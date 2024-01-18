import numpy as np

from scipy.sparse import diags, lil_matrix,csr_matrix
from scipy.sparse import spdiags

class Mimetic():
    def __init__(self, mesh):
        self.mesh = mesh
    
    def M_f(self, ac=None):
        mesh = self.mesh
        #GD = mesh.geo_dimension()
        NC = mesh.number_of_cells()
        NE = mesh.number_of_edges()
        cell2edge = mesh.ds.cell_to_edge()
        norm = mesh.edge_unit_normal()
        #print("norm:", norm.shape, "\n", norm)
        edge_centers = mesh.entity_barycenter(etype=1)
        cell_centers = mesh.entity_barycenter(etype=2) # (NC, GD)
        #norm_flag = np.where(mesh.ds.cell_to_edge_sign().toarray(),1,-1)
        flag = np.where(mesh.ds.cell_to_edge_sign().toarray(), 1, -1)
        edge_measure = mesh.entity_measure(etype=1)
        cell_measure = mesh.entity_measure(etype=2)
        result = np.zeros((NE, NE))
        if ac is None:
            ac = cell_measure
        
        for i in range(NC):
            LNE = len(cell2edge[i])
            #R = np.zeros((LNE, GD))
            #N = np.zeros((LNE, GD))
            cell_out_flag = flag[i][cell2edge[i]] # (LNE, )
            cell_edge_measure = edge_measure[cell2edge[i]] # (LNE, )
            cell_edge_centers = edge_centers[cell2edge[i]] # (LNE, GD)
            R = np.einsum('l, lg, l -> lg', cell_out_flag, cell_edge_centers-cell_centers[i, :], cell_edge_measure) # (LNE, GD)
            N = norm[cell2edge[i], :] # (LNE, GD)

            #for j, edge_index in enumerate(cell2edge[i]):
                #R[j, :] = (edge_centers[edge_index,:] - cell_centers[i,:]) * edge_measure[edge_index]
                #N[j, :] = norm_flag[i,edge_index]*norm[edge_index]
                #R[j, :] = norm_flag[i, edge_index]*(edge_centers[edge_index,:] - cell_centers[i,:]) * edge_measure[edge_index]
                #N[j, :] = norm[edge_index]
            #print("R_test:", R1-R)
            #print("N_test:", N1-N)

            #M_consistency = R@R.T/cell_measure[i]
            M_consistency = R @ np.linalg.inv(R.T @ N) @ R.T
            #M_stability = ac[i] * (np.eye(LNE) - N @ np.linalg.inv(N.T @ N) @ N.T)
            M_stability = np.trace(R@R.T) /cell_measure[i] * (np.eye(LNE) - N @ np.linalg.inv(N.T @ N) @ N.T)
            M = M_consistency + M_stability # (LNE, LNE)
            #print("M:", M.shape, "\n", M)
            '''
            print(f"第{i}个单元")
            print(np.linalg.eigvals(M))
            print(np.max(np.abs(M-M.T)))
            print(np.max(np.abs(M@N-R)))
            A  = np.zeros((LNE, NE))
            '''
            indexi, indexj = np.meshgrid(cell2edge[i], cell2edge[i])
            result[indexi, indexj] += M 

        return result
    
    def M_c(self):
        mesh = self.mesh
        cell_measure = mesh.entity_measure("cell")
        result = np.diag(cell_measure)

        return result
    
    def div_operate(self):
        mesh = self.mesh
        NC = mesh.number_of_cells()
        NE = mesh.number_of_edges()
        cell_measure = mesh.entity_measure(etype=2)
        edge_measure = mesh.entity_measure(etype=1)
        cell2edge = mesh.ds.cell_to_edge()
        print("cell2edge:\n", cell2edge)
        #cell_out_normal = self.cell_out_normal()
        flag = np.where(mesh.ds.cell_to_edge_sign().toarray(), 1, -1)
        result = np.zeros((NC, NE))
        for i in range(NC):
            cell_out_flag = flag[i][cell2edge[i]] # (LNE, )
            print("cell_out_flag:", cell_out_flag.shape, "\n", cell_out_flag)
            cell_edge_measure = edge_measure[cell2edge[i]] # (LNE, )
            print("cell_edge_measure:", cell_edge_measure.shape, "\n", cell_edge_measure)
            result[i, cell2edge[i]] = cell_out_flag * cell_edge_measure/cell_measure[i]
        return result
    
    def source(self, fun, gddof, D):
        mesh = self.mesh
        NE = mesh.number_of_edges()
        cell_centers = mesh.entity_barycenter(etype=2)
        cell_measure = mesh.entity_measure('cell') 
        
        edge_measure = mesh.entity_measure('edge') 
        edge_centers = mesh.entity_barycenter(etype=1)
        #result = mesh.integral(fun,q=5,celltype=True)

        f = fun(cell_centers)
        b = cell_measure * f
        #print("b:", b.shape, "\n", b)
        #b1 = np.diag(cell_measure) * f
        #print("b1:", b1.shape, "\n", b1)
        #print("b-b1:", b-b1)

        gamma = np.zeros(NE)
        gamma[gddof] = edge_measure[gddof] * D(edge_centers[gddof])
        result = np.hstack((-gamma, -b))

        return result
    

    def boundary_treatment(self, A, b, Df, isDcelldof, Nf=None, isNedgedof=None, so=None):
        mesh = self.mesh
        NE = mesh.number_of_edges()
        NC = mesh.number_of_cells()
        gdof = NE+NC
        cell_centers = mesh.entity_barycenter(etype=2)
        edge_centers = mesh.entity_barycenter(etype=1)
        
        isBdDof = np.hstack(([False]*NE, isDcelldof))
        if isNedgedof is not None:
            isBdDof = np.hstack([isNedgedof,isDcelldof])
        
        bdIdx = np.zeros(gdof, dtype=np.int_)
        bdIdx[isBdDof] = 1
        Tbd = spdiags(bdIdx, 0, gdof, gdof).toarray()
        T = spdiags(1-bdIdx, 0, gdof, gdof).toarray()
        A = T@A + Tbd
        
        xx = np.zeros((gdof,),dtype=np.float64)
        xx[:NE] = 0
        if isNedgedof is not None:
            xx[0:NE][isNedgedof] = Nf(edge_centers[isNedgedof])
        xx[NE:][isDcelldof] = Df(cell_centers[isDcelldof])
        #xx[NE:][isDcelldof] = so[isDcelldof]
        b[isBdDof] = xx[isBdDof]
        return A,b

    def cell_out_normal(self):
        mesh = self.mesh
        
        cell2edge = mesh.ds.cell_to_edge()
        normal = mesh.edge_unit_normal()
        flag = np.where(mesh.ds.cell_to_edge_sign().toarray(), 1, -1)

        cellnormal = [[normal[edge] for edge in cell] for cell in cell2edge]
        osign = [flag[i, edges] for i, edges in enumerate(cell2edge)]
        celloutnormal = [arr1 * arr2[:,None] for arr1, arr2 in zip(cellnormal, osign)]
        return celloutnormal


