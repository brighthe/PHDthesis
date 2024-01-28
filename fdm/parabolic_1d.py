import numpy as np

from fealpy.decorator import cartesian

class Sin4PiExpData:
    def __init__(self, D=[0, 1], T=[0, 1]):
        """
        @brief 模型初始化函数
        @param[in] D 模型空间定义域
        @param[in] T 模型时间定义域
        """
        self._domain = D 
        self._duration = T 

    def domain(self):
        """
        @brief 空间区间
        """
        return self._domain

    def duration(self):
        """
        @brief 时间区间
        """
        return self._duration 
        
    @cartesian
    def solution(self, p, t):
        """
        @brief 真解函数

        @param[in] p numpy.ndarray, 空间点
        @param[in] t float, 时间点 

        @return 真解函数值
        """
        pi = np.pi
        return np.sin(4*pi*p)*np.exp(-10*t) 

    @cartesian
    def init_solution(self, p):
        """
        @brief 真解函数

        @param[in] p numpy.ndarray, 空间点
        @param[in] t float, 时间点 

        @return 真解函数值
        """
        pi = np.pi
        return np.sin(4*pi*p) 
        
    @cartesian
    def source(self, p, t):
        """
        @brief 方程右端项 

        @param[in] p numpy.ndarray, 空间点
        @param[in] t float, 时间点 

        @return 方程右端函数值
        """
        pi = np.pi
        return -10*np.exp(-10*t)*np.sin(4*pi*p) + 16*pi**2*np.exp(-10*t)*np.sin(4*pi*p)
    
    @cartesian
    def gradient(self, p, t):
        """
        @brief 真解导数 

        @param[in] p numpy.ndarray, 空间点
        @param[in] t float, 时间点 

        @return 真解导函数值
        """
        pi = np.pi
        return 4*pi*np.exp(-10*t)*np.cos(4*pi*p)

    
    @cartesian    
    def dirichlet(self, p, t):
        """
        @brief Dirichlet 边界条件

        @param[in] p numpy.ndarray, 空间点
        @param[in] t float, 时间点 
        """
        return self.solution(p, t)

    @cartesian
    def is_dirichlet_boundary(self, p):
        """
        @brief Dirichlet 边界的判断函数
        """
        flag = (np.abs(p - 1.0) < 1e-12) | (np.abs(p - 0.0) < 1e-12)

        return flag

