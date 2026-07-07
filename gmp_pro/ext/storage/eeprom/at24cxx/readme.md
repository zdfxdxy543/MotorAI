# Extension library of GMP for EEPROM AT24Cxx series

This folder contain a driver of AT24Cxx series EEPROM chip.
This driver will make you access EEPROM chip easily.

This driver only support general the first generation chip of EEPROM,
that is AT24C02, AT24C04, AT24C08, AT24C16  is support.

> You may get the user manual of these chip here:
>
> https://ww1.microchip.com/downloads/en/devicedoc/doc0180.pdf
>

This is a device on the I2C bus, so you should have a I2C bus first.
I2C bus is a class which derived from `gmp_iic_entity` class.
The construction function need a pointer to `gmp_iic_entity` class.

Also, you have to know the chip model.


## Examples

For instance, you have a AT24C04 EEPROM chip, you have correctly complete the physical connection on a STM32 chip.

> DO NOT leave the pull-up resistor of the SCL & SDA wire.
> Otherwise IIC bus arbiter of some chip (for example, STM32) will go on strike, showing BUSY status all the time.

And then, you should have a IIC implement.

``` C++
// peripheral_mapping.hpp
extern gmp_iic_stm32_impl_t iic;

// peripherl_mapping.cpp
gmp_iic_stm32_impl_t iic(&hi2c1);

```

Then you may use the implement of IIC to initialize a EEPROM object.

``` C++
// headers here
#include <ext/eeprom/at24cxx/at24cxx.h>

// object definitions here
at24cxx eeprom04(
	&iic,				// param1: the IIC bus will link to
	at24cxx::at24c04,	// param2: The chip model
	0					// param3: The physical address of the chip
	);

```
 NOTE param3 is decided by physical linkage of A0, A1, A2 pin.

And now, you can access the EEPROM in a very easy way.

``` C++
	// the first parameter is the address, 
	// the second parameter is the data
	eeprom04.write(255, 0x17);
	eeprom04.write(254, 0x18);
	eeprom04.write(253, 0x19);

	// You only need to provide the address, and the return value is the data stored in EEPROM.
	uint32_t result = eeprom04.read(253);
	gmp_dbg_prt("result: %x, error code: %d.\r\n", result,eeprom04.iic->last_error);
	// You will see: result: 19, error code: 0.

	// Try another address
	result = eeprom04.read(254);
	gmp_dbg_prt("result: %x, error code: %d.\r\n", result,eeprom04.iic->last_error);
	// You will see: result: 18, error code: 0.
```


