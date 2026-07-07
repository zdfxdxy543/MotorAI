# GMP peripheral extension module



This folder provide a lot of peripherals, User may use these modules directly via GMP general interface. 

If a chip has a valid CSP module, the `ext` module will vary easy to use.



## Summary of Ext module

Ext module provide a lot of single chip peripherals, including ADC, DAC, motor encoder, DDS, power manager, sensor and etc. .

| Submodule                              | folder          | Summary                                                      |
| -------------------------------------- | --------------- | ------------------------------------------------------------ |
| ADC<br />(Analog-to-digital converter) | `ext/adc`       | ADC chip with SPI interface, IIC interface, parallel interface. |
| DAC<br />(Digital-to-analog converter) | `ext/dac`       | DAC chip with SPI interface, IIC interface, parallel interface. |
| DDS<br />(Direct Digital Synthesizer)  | `ext/dds`       | DDS chip with SPI interface.                                 |
| Other Analog Devices                   | `ext/analog`    | Some analog MUX chip, Digitally Controlled Potemiometer (DCP). |
| Communication Related                  | `ext/comm`      | Communication extension. Such as SPI to Ethernet, SPI to CAN, SPI to LoRa, SPI to  EtherCAT, UART to RS485, IIS interface. |
| IO Extension                           | `ext/io_ext`    | IO extension module. These chips support user to extend their low speed IO interface via IIC interface or SPI interface. |
| Power Manager                          | `ext/power_mgr` | Power Management module. This module provide chip power management and auto reset. |
| Sensors                                | `ext/sensor`    | There're several sensors, such as temperature, humidity, light and some others. |
| Display                                | `ext/display`   | Display module to drive LED or e-paper and etc. .            |
| Motor Encoder                          | `ext/encoder`   | Motor Encoder                                                |
| Storage Module                         | `ext/storage`   | Storage module, such as EEPROM, SPI FLASH, and some other modules. |





##  Details of Each Sub-modules

## Code standard

All the GMP extension modules' function has an prefix `gmpe_`, that is GMP Extention.

For initialize function, `gmpe_init_<module/chip name>` is the standard name.所有的ext模块需要以`gmpe_`作为开头，同时每一个模块应当至少实现init和setup两个函数，init函数需要初始化（分配内存和初值），setup函数需要为模块赋予初值。

| Function Name           | Note                 |
| ----------------------- | -------------------- |
| `gmpe_<PartName>_init`  | 初始化一个外设对象   |
| `gmpe_<PartName>_setup` | 初步配置一个外设对象 |

For other utilities function, `gmpe_<module/chip name>_<do>[_<target>]` is the standard name.
For instantce, `<do>` can be change to `request`, `get`, `set` and etc. .其他可用函数有

| Function Name                                            | Note                   |
| -------------------------------------------------------- | ---------------------- |
| `gmpe_<PartName>_get`, `gmpe_<PartName>_set`             | 设置，获得本地的参数   |
| `gmpe_<PartName>_request`, `gmpe_<PartName>_sync_config` | 同步、获得外设端的参数 |
| `gmpe_<PartName>_read`, `gmpe_<PartName>_write`          | 对外设进行读写         |





