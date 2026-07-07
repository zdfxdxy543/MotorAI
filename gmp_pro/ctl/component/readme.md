# GMP CTL Components Source folder

This Folder contains all the components provided by GMP CTL.
This folder provide several types of components for user to build a control law quickly.

GMP CTL Components Root Directory.



在CTL的器件库中每一个器件需要提供如下三个基本函数

| Function                                                     | Note                                                         | Comment           |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ----------------- |
| `void ctl_init_<component>(<component handle>)`              | 初始化函数，只是初始化基础的内存空间，验证指针是否可用，或者分配内存。将原件初始化至clear的状态。 |                   |
| `<ret type> ctl_step_<component>(<component handle>. <input target>)` | 让元件运行一步。返回值为运算结果，通常返回值只对标量返回值有效。 | GMP_STATIC_INLINE |



以下的函数可以根据需要增加

| Function                                                     | Note                                                         | Comment           |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ----------------- |
| `void ctl_clear_<component>(<component handle>)`             | 将对象初始化到0状态，保持原件的参数。                        | GMP_STATIC_INLINE |
| `<ret type> ctl_helper_<component>(<parameters>)`            | helper function用来进行器件的中间步骤计算。                  |                   |
| `<ret value> ctl_get_<component>_<param>(<component handle>)` | 得到特定器件的特定参数，通过返回值得到标量参数，通过参数指针返回向量参数。 |                   |
| `void ctl_set_<component>_<param>(<component handle>, target)` | 设定特定器件的特定参数，在有必要的情况下对参数范围进行检查。 |                   |
| `fast_gt ctl_is_<component>_<flag>(<component handle>)`      | 判定控制器的某个标志位是否置位                               |                   |
| `void ctl_attach_<component>_<port>(<component handle>, <interface type pointer>)` | 将某一个接口类型绑定在控制器上，主要引用于成套的控制器       |                   |





## CTL math block 模块

在CTL的math_block中构建，通过包含头文件`<ctl_math.h>`引入CTL的数学支持库。CTL模块中所有的子模块和组件都是基于CTL math block实现的。

其中，支持以下几个基本基础功能。



### CTL控制器类型计算支持

在`<gmp_math.h>`文件中给出了对于`ctrl_gt`类型的运算支持。下面给出常用的基础函数



| Function Name          | Note                                                         |
| ---------------------- | ------------------------------------------------------------ |
| `float2ctrl(x)`        | 将x（通常是浮点类型）转换为`ctrl_gt`类型，通常用于变量的初始化和常数的定义 |
| `ctrl2float(x)`        | 将ctrl类型转换为float类型                                    |
| `int2ctrl(A)`          | 将`int`类型转接为`ctrl_gt`类型                               |
| `ctrl2int(A)`          | 进行类型转换，获得`ctrl_gt`类型的整数部分                    |
| `ctl_mod_1(A)`         | 获得`ctrl_gt`类型的小数部分                                  |
| `ctl_mul(A,B)`         | 计算`ctrl_gt`类型的乘法，结果为`(A*B)`                       |
| `ctl_div(A,B)`         | 计算`ctrl_gt`类型的除法，结果为`(A/B)`                       |
| `ctl_sat(A, POS, NEG)` | 将数值A进行限幅，通常是借助宏`saturation_macro()`实现的（基本原理是`ctrl_gt`能够保持比较运算不变） |
| `ctl_div2(A)`          | 计算A/2的值                                                  |
| `ctl_div4(A)`          | 计算A/4的值                                                  |



在比较极端的情况下，可能需要加法和减法函数，通常情况下，对于加减法我们通常会默认是成立的，兼容下面所述两个函数的模块有限。

但是这两个函数是必要的，因为在不具备FPU的设备中，必须要借助如下两个函数实现加法和减法。

| Function Name   | Note                                   |
| --------------- | -------------------------------------- |
| `ctl_add(A, B)` | 计算`ctrl_gt`类型的加法，结果为`(A+B)` |
| `ctl_sub(A ,B)` | 计算`ctrl_gt`类型的加法，结果为`(A-B)` |





### const Module

定义了全部CTL中需要使用的常数。

`<math_ctrl_const_param.h>`中定义了所有控制中需要的常数。

`<math_float_const_param.h>`中定义了所有控制中需要的至少为浮点数的常数。



### nonlinear Module

非线性模块提供了三角函数、指数函数等的计算表达。

下面给出了需要支持的非线性函数的类型：

| Function Name    | Note                                                         |
| ---------------- | ------------------------------------------------------------ |
| `ctl_sin(A)`     | 计算正弦`ctl_sin(A)`输入的类型和输出的类型均为`ctrl_gt`，A的单位为标幺，1.0 = 360\degree |
| `ctl_cos(A)`     | 计算余弦`ctl_cos(A)`输入类型和输出类型均为`ctrl_gt`，角度A的单位为标幺，1.0 = 360\degree |
| `ctl_tan(A)`     | 计算正切`ctl_tan(A)`输入类型和输出类型均为`ctrl_gt`，角度A的单位为标幺，1.0 = 360\degree |
| `ctl_atan2(y,x)` | 计算反正切`ctl_atan(y,x)`输入类型和输出类型均为`ctrl_gt`，输出角度tan A = y/x，单位为标幺，1.0 = 360\degree |
| `ctl_exp(x)`     | 计算指数函数，输入输出类型均为`ctrl_gt`                      |
| `ctl_ln(x)`      | 计算对数函数，输入输出类型均为`ctrl_gt`                      |
| `ctl_sqrt(x)`    | 计算开根函数，输入输出类型均为`ctrl_gt`                      |
| `ctl_isqrt(x)`   | 计算开根函数的倒数，输入输出类型均为`ctrl_gt`                |

 



### coordinate Module

提供坐标变换相关的数学计算过程



### complex Module

复数计算模块



### vector Module

向量计算模块，提供2维、3维、4维的向量操作



### matrix Module

矩阵计算模块，matrix提供2维，3维，4维的矩阵计算模块


用户可以通过阅读component文件夹下的几个头文件快速找到自己需要的功能模块。
