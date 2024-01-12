import argparse
import os
import matplotlib.pyplot as plt
import numpy as np

from scipy.sparse.linalg import spsolve

from fealpy.pde.linear_elasticity_model import BoxDomainData
from fealpy.functionspace import LagrangeFESpace as Space

from fealpy.fem import LinearElasticityOperatorIntegrator
from fealpy.fem import VectorSourceIntegrator
from fealpy.fem import VectorMassIntegrator
from fealpy.fem import BilinearForm
from fealpy.fem import LinearForm
from fealpy.fem import DirichletBC


## 参数解析
parser = argparse.ArgumentParser(description=
        """
        单纯形网格（三角形、四面体）网格上任意次有限元方法
        """)

parser.add_argument('--degree',
        default=1, type=int,
        help='Lagrange 有限元空间的次数, 默认为 1 次.')

parser.add_argument('--GD',
        default=2, type=int,
        help='模型问题的维数, 默认求解 2 维问题.')

parser.add_argument('--nrefine',
        default=2, type=int,
        help='初始网格加密的次数, 默认初始加密 2 次.')

parser.add_argument('--scale',
        default=1, type=float,
        help='网格变形系数，默认为 1')

parser.add_argument('--doforder',
        default='vdims', type=str,
        help='自由度排序的约定，默认为 vdims')

args = parser.parse_args()
p = args.degree
GD = args.GD
n = args.nrefine
scale = args.scale
doforder = args.doforder

pde = BoxDomainData()

mu = pde.mu
lambda_ = pde.lam
domain = pde.domain()
mesh = pde.delaunay_mesh()
#import matplotlib.pyplot as plt
#fig = plt.figure()
#axes = fig.gca()
#mesh.add_plot(axes)
#mesh.find_cell(axes, showindex=True, color='k', marker='s', markersize=2, fontsize=8, fontcolor='k')
#mesh.find_node(axes, showindex=True, color='r', marker='o', markersize=2, fontsize=8, fontcolor='r')
#plt.show()
NN = mesh.number_of_nodes()
print("NN:", NN)
NC = mesh.number_of_cells()
print("NC:", NC)
node = mesh.entity('node')
cell = mesh.entity('cell')
print("cell:\n", cell.shape, "\n", cell)

output = './mesh/'
if not os.path.exists(output):
    os.makedirs(output)
fname = os.path.join(output, 'DelaunayMesh.vtu')

space = Space(mesh, p=p, doforder=doforder)
uh = space.function(dim=GD)
vspace = GD*(space, )
gdof = vspace[0].number_of_global_dofs()
vgdof = gdof * GD
ldof = vspace[0].number_of_local_dofs()
vldof = ldof * GD
print("vgdof", vgdof)
print("vldof", vldof)

integrator1 = LinearElasticityOperatorIntegrator(lam=lambda_, mu=mu, q=p+1)

bform = BilinearForm(vspace)
bform.add_domain_integrator(integrator1)
KK = integrator1.assembly_cell_matrix(space=vspace)
print("KK", KK.shape)
bform.assembly()
K = bform.get_matrix()
print("K:", K.shape, "\n", K.toarray().round(4))

integrator2 = VectorMassIntegrator(c=1, q=5)

bform2 = BilinearForm(vspace)
bform2.add_domain_integrator(integrator2)
MK = integrator2.assembly_cell_matrix(space=vspace)
print("MK:", MK.shape)
bform2.assembly()
M = bform2.get_matrix()
print("M:", M.shape)

integrator3 = VectorSourceIntegrator(f = pde.source, q=5)

lform = LinearForm(vspace)
lform.add_domain_integrator(integrator3)
FK = integrator3.assembly_cell_vector(space = vspace)
print("FK[0]:", FK.shape)
lform.assembly()
F = lform.get_vector()
print("F:", F.shape, "\n", F.round(4))

ipoints = space.interpolation_points()
fh = pde.source(p=ipoints)
fh_1 = np.zeros(M.shape[0])
fh_1[::GD] = fh[:,0]
fh_1[1::GD] = fh[:,1]
Fh = M @ fh_1
print("Fh:", Fh.shape, "\n", Fh.round(4))

print("error:", np.sum(np.abs(F - Fh)))

if hasattr(pde, 'dirichlet'):
    bc = DirichletBC(space=vspace, gD=pde.dirichlet, threshold=pde.is_dirichlet_boundary)
    K, Fh = bc.apply(K, Fh, uh)

print("K:", K.shape, "\n", K.toarray().round(4))
print("Fh:", Fh.shape, "\n", Fh.round(4))

uh.flat[:] = spsolve(K, Fh)
print("uh:", uh.shape, uh)

reshaped_uh = uh.reshape(-1)
cell2dof = space.cell_to_dof()
print("cell2dof:", cell2dof.shape, "\n", cell2dof)
updated_cell2dof = np.repeat(cell2dof * GD, GD, axis=1) + np.tile(np.array([0, 1]), (NC, ldof))
cell_displacements = reshaped_uh[updated_cell2dof] # (NC, ldof*GD)
print("cell_displacements:", cell_displacements.shape, "\n", cell_displacements)

qf =  mesh.integrator(p+1, 'cell')
bcs, ws = qf.get_quadrature_points_and_weights()
grad = space.grad_basis(bcs) # (NQ, NC, ldof, GD)
print("grad:", grad.shape, "\n", grad)

import numpy as np

def compute_strain(grad, cell_displacement):
    """
    参数:
    grad (np.ndarray): 形状函数梯度，形状为 (NQ, NC, ldof, GD)
    cell_displacement (np.ndarray): 单元位移，形状为 (NC, ldof*GD)
    返回:
    np.ndarray: 应变矩阵
    """
    NQ, NC, ldof, GD = grad.shape
    strain_dim = GD * (GD + 1) // 2
    strain = np.zeros((NQ, NC, strain_dim))

    # (NC, ldof*GD) -> (NC, ldof, GD)
    cell_displacement_reshaped = cell_displacement.reshape(1, NC, ldof, GD)

    # 对于二维和三维问题，使用不同的索引策略
    if GD == 2:
        # 二维应变计算 (ε_xx, ε_yy, γ_xy)
        strain[:, :, 0] = np.sum(grad[:, :, :, 0] * cell_displacement_reshaped[:, :, :, 0], axis=2)  # ε_xx
        strain[:, :, 1] = np.sum(grad[:, :, :, 1] * cell_displacement_reshaped[:, :, :, 1], axis=2)  # ε_yy
        strain[:, :, 2] = np.sum(grad[:, :, :, 0] * cell_displacement_reshaped[:, :, :, 1] +
                                 grad[:, :, :, 1] * cell_displacement_reshaped[:, :, :, 0], axis=2)  # γ_xy
    elif GD == 3:
        # 三维应变计算 (ε_xx, ε_yy, ε_zz, γ_xy, γ_yz, γ_xz)
        for i in range(GD):
            strain[:, :, i] = np.sum(grad[:, :, :, i] * cell_displacement_reshaped[:, :, :, i], axis=2)  # ε_xx, ε_yy, ε_zz
        strain[:, :, 3] = np.sum(grad[:, :, :, 0] * cell_displacement_reshaped[:, :, :, 1] +
                                 grad[:, :, :, 1] * cell_displacement_reshaped[:, :, :, 0], axis=2)  # γ_xy
        strain[:, :, 4] = np.sum(grad[:, :, :, 1] * cell_displacement_reshaped[:, :, :, 2] +
                                 grad[:, :, :, 2] * cell_displacement_reshaped[:, :, :, 1], axis=2)  # γ_yz
        strain[:, :, 5] = np.sum(grad[:, :, :, 0] * cell_displacement_reshaped[:, :, :, 2] +
                                 grad[:, :, :, 2] * cell_displacement_reshaped[:, :, :, 0], axis=2)  # γ_xz

    return strain

strain = compute_strain(grad=grad, cell_displacement=cell_displacements)
print("strain:", strain.shape, "\n", strain)

def compute_stress(mu, lam, strain):
    """
    参数:
    strain (np.ndarray): 应变矩阵，形状为 (NQ, NC, strain_dim)
    返回:
    np.ndarray: 应力矩阵
    """
    strain_dim = strain.shape[-1]
    if strain_dim == 3:
        # 二维应力计算
        D = np.array([
            [2*mu+lam, lam, 0],
            [lam, 2*mu+lam, 0],
            [0, 0, mu]
        ])
    elif strain_dim == 6:
        # 三维应力计算
        D = np.array([
            [2*mu+lam, lam, lam, 0, 0, 0],
            [lam, 2*mu+lam, lam, 0, 0, 0],
            [lam, lam, 2*mu+lam, 0, 0, 0],
            [0, 0, 0, mu, 0, 0],
            [0, 0, 0, 0, mu, 0],
            [0, 0, 0, 0, 0, mu]
        ])
    stress = np.einsum('qck, kl -> qcl', strain, D)

    return stress

stress = compute_stress(mu=mu, lam=lambda_, strain=strain)
print("stress:", stress.shape, "\n", stress)




mesh.nodedata['u'] = uh[:, 0]
mesh.nodedata['v'] = uh[:, 1]

mesh.to_vtk(fname=fname)
