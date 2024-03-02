import numpy as np

from fealpy.mesh import QuadrangleMesh

# Cantilever
class TopRBFPlsm:

    def __init__(self, nelx: int = 60, nely: int = 30, volfrac: float = 0.5):
        '''
        初始化拓扑优化问题

        Parameters: 
        - nelx (int): 沿设计区域水平方向的单元数.
        - nely (int): 沿设计区域垂直方向的单元数.
        - volfrac (float) : 规定的体积分数.
        '''

        self._nelx = nelx
        self._nely = nely
        self._volfrac = volfrac

        self._mesh = QuadrangleMesh.from_box(box = [0, self._nelx, 0, self._nely], \
                                        nx = self._nelx, ny = self._nely)

    def lsf_init(self, mesh):
        '''
        水平集函数初始化
        Parameters: 

        '''
        nelx = self._nelx
        nely = self._nely

        node = mesh.entity('node') # 按列增加
        # 网格中节点的 x 坐标 - (nely+1, nelx+1)
        X = node[:, 0].reshape(nelx+1, nely+1).T
        #print("X:", X.shape, "\n", X)
        # 网格中节点的 y 坐标 - (nely+1, nelx+1)
        Y = node[:, 1].reshape(nelx+1, nely+1).T
        #print("Y:", Y.shape, "\n", Y)
        # 初始孔洞的半径
        r = nely * 0.1
        # hX 是初始孔洞的中心处的 x 坐标 - (15, )
        hX = nelx * np.concatenate([np.tile([1/6, 5/6], 3), np.tile([0, 1/3, 2/3, 1], 2), [1/2]])
        #print("hX:", hX.shape, "\n", hX)
        # hY 是初始孔洞的中心处的 y 坐标 - (15, )
        hY = nely * np.concatenate([np.repeat([0, 1/2, 1], 2), np.repeat([1/4, 3/4], 4), [1/2]])
        #print("hY:", hY.shape, "\n", hY)

        # dX 是所有网格点在 x 方向上与初始孔洞的中心之间的距离差, 形状为 (nely+1, nelx+1, 15)
        dX = X[:, :, np.newaxis] - hX
        #print("dX:", dX.shape, "\n", dX)
        # dY 是所有网格点在 Y 方向上与初始孔洞的中心之间的距离差, 形状为 (nely+1, nelx+1, 15)
        dY = Y[:, :, np.newaxis] - hY
        #print("dY:", dY.shape, "\n", dY)

        # 计算网格点到最近孔洞附近的欧氏距离，并限制在 -3 到 3 之间
        Phi = np.sqrt(dX**2 + dY**2) - r
        Phi = np.min(Phi, axis=2)
        Phi = np.clip(Phi, -3, 3)

        return Phi

    def rbf_init(self, mesh, Phi):
        '''
        径向基函数初始化
        '''
        nelx = self._nelx
        nely = self._nely
        
        # RBF 参数
        cRBF = 1e-4

        node = mesh.entity('node') # 按列增加
        # 网格中节点的 x 坐标 - (nely+1, nelx+1)
        X = node[:, 0].reshape(nelx+1, nely+1).T
        # 网格中节点的 y 坐标 - (nely+1, nelx+1)
        Y = node[:, 1].reshape(nelx+1, nely+1).T

        # MQ 样条组成的矩阵 A - ((nely+1)*(nelx+1), (nely+1)*(nelx+1))
        Ax = np.subtract.outer(X.flatten('F'), X.flatten('F')) # 所有节点间 x 方向的距离差
        Ay = np.subtract.outer(Y.flatten('F'), Y.flatten('F')) # 所有节点间 y 方向的距离差
        A = np.sqrt(Ax**2 + Ay**2 + cRBF**2)
        #print("A:", A.shape, "\n", A.round(4))

        # 构建矩阵 G - ((nely+1)*(nelx+1)+3, (nely+1)*(nelx+1)+3)
        nNode = mesh.number_of_nodes() # 节点总数
        P = np.vstack((np.ones(nNode), X.flatten('F'), Y.flatten('F'))).T
        I = np.zeros((3, 3))
        G_upper = np.hstack((A, P))
        G_lower = np.hstack((P.T, I))
        G = np.vstack((G_upper, G_lower))
        #print("G:", G.shape, "\n", G.round(4))

        # MQ 样条在 x 方向上的偏导数组成的矩阵 pGpX - ((nely+1)*(nelx+1)+3, (nely+1)*(nelx+1)+3)
        pGpX_upper = np.hstack((Ax / A, np.tile(np.array([0, 1, 0]), (nNode, 1))))
        pGpX_lower = np.hstack((np.tile(np.array([[0], [1], [0]]), (1, nNode)), np.zeros((3, 3))))
        pGpX = np.vstack((pGpX_upper, pGpX_lower))

        # MQ 样条在 y 方向上的偏导数组成的矩阵 pGpY - ((nely+1)*(nelx+1)+3, (nely+1)*(nelx+1)+3)
        pGpY_upper = np.hstack((Ay / A, np.tile(np.array([0, 0, 1]), (nNode, 1))))
        pGpY_lower = np.hstack((np.tile(np.array([[0], [0], [1]]), (1, nNode)), np.zeros((3, 3))))
        pGpY = np.vstack((pGpY_upper, pGpY_lower))

        # 广义展开系数 Alpha - ((nely+1)*(nelx+1)+3, )
        Phi_flat = Phi.flatten('F')
        Alpha = np.linalg.solve(G, np.hstack((Phi_flat, np.zeros(3))))

        return A, G, pGpX, pGpY, Alpha

    def FE(self, mesh, eleVol, KE, F, fixeddofs):
        from plsf_beam_operator_integrator import BeamOperatorIntegrator
        from fealpy.fem import BilinearForm
        from fealpy.functionspace import LagrangeFESpace as Space
        from scipy.sparse import spdiags
        from scipy.sparse.linalg import spsolve

        p = 1
        space = Space(mesh, p=p, doforder='vdims')
        GD = 2
        uh = space.function(dim=GD)
        vspace = GD*(space, )
        gdof = vspace[0].number_of_global_dofs()
        ldof = vspace[0].number_of_local_dofs()

        nu = 0.3
        E0 = 1.0
        Emin = 1e-9
        integrator = BeamOperatorIntegrator(nu=nu, E0=E0, Emin=Emin, eleVol=eleVol, KE=KE)
        bform = BilinearForm(vspace)
        bform.add_domain_integrator(integrator)
        KK = integrator.assembly_cell_matrix(space=vspace)
        bform.assembly()
        K = bform.get_matrix()
        #print("K2:", K.shape, "\n", K.toarray().round(4))

        dflag = fixeddofs
        F = F - K@uh.flat
        bdIdx = np.zeros(K.shape[0], dtype=np.int_)
        bdIdx[dflag.flat] = 1
        D0 = spdiags(1-bdIdx, 0, K.shape[0], K.shape[0])
        D1 = spdiags(bdIdx, 0, K.shape[0], K.shape[0])
        K = D0@K@D0 + D1
        F[dflag.flat] = uh.ravel()[dflag.flat]

        # 线性方程组求解
        uh.flat[:] = spsolve(K, F)

        reshaped_uh = uh.reshape(-1)
        cell2dof = vspace[0].cell_to_dof()
        NC = mesh.number_of_cells()
        updated_cell2dof = np.repeat(cell2dof*GD, GD, axis=1) + np.tile(np.array([0, 1]), (NC, ldof))
        idx = np.array([0, 1, 4, 5, 6, 7, 2, 3], dtype=np.int_)
        # 用 Top 中的自由度替换 FEALPy 中的自由度
        updated_cell2dof = updated_cell2dof[:, idx]
        ue = reshaped_uh[updated_cell2dof] # (NC, ldof*GD)

        return uh, ue




