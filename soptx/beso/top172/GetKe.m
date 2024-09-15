%% 单元刚度矩阵
function [Ke] = GetKe(X, Y, E0, nu)
    % 贴体三角形网格的刚度矩阵，与传统方法中的结构化矩形网格不同，
    % 非结构化网格中固体材料的单元刚度矩阵根据顶点坐标而变化
    % 输入参数：
    % X, Y - (ldof, ): 单元中三角形节点的坐标
    % 输出参数：
    % Ke - (ldof*GD, ldof*GD): 三节点的单元刚度矩阵
    D = E0 / (1-nu^2) * [1 nu 0; nu 1 0; 0 0 (1-nu)/2];
    J = [X(1)-X(3) Y(1)-Y(3); X(2)-X(3) Y(2)-Y(3)];
    Be = 1/det(J) * [J(2,2) 0 -J(1,2) 0 -J(2,2)+J(1,2) 0;
                     0 -J(2,1) 0 J(1,1) 0 J(2,1)-J(1,1);
                     -J(2,1) J(2,2) J(1,1) -J(1,2) J(2,1)-J(1,1) -J(2,2)+J(1,2)];
    Ke = 1/2*det(J)*Be'*D*Be; 
end