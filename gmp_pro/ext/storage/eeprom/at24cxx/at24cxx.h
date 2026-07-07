
#ifndef _FILE_AT24CXX_H_
#define _FILE_AT24CXX_H_

// This device is for ATMEL AT24Cxx(xx = 01,02,04,08,16)
class at24cxx final
	:public iic_storage_device_t
{
public:
	// ctor & dtor
	at24cxx(gmp_iic_entity* iic,
		uint8_t device_type,
		uint16_t ext_addr = 0)
		:iic_storage_device_t(iic, base_address, 1)
	{
		// less than 3 bits.
		assert(ext_addr < 0x07);

		switch (device_type)
		{
		case at24c01:
			dev_addr = base_address | (0x07 & ext_addr);
			higher_mask = 0x00;
			break;
		case at24c02:
			dev_addr = base_address | (0x07 & ext_addr);
			higher_mask = 0x00;
			break;
		case at24c04:
			dev_addr = base_address | (0x06 & ext_addr);
			higher_mask = 0x01;
			break;
		case at24c08:
			dev_addr = base_address | (0x04 & ext_addr);
			higher_mask = 0x03;
			break;
		case at24c16:
			dev_addr = base_address;
			higher_mask = 0x07;
			break;
		default:
			gmp_dbg_prt("ERROR:Incompatible EEPROM devices.\r\n");
		}


	}

public:
	// Basic read & write function

	virtual cell_type read(addr_type addr);

	virtual size_gt write(addr_type addr, cell_type data);

	virtual size_gt read(addr_type addr, data_type* data, size_gt length);

	virtual size_gt write(addr_type addr, data_type* data, size_gt length);

public:
	// Higher address mask
	addr_gt higher_mask;

public:
	// constant
	static constexpr uint8_t page_size = 8;  // bytes
	static constexpr uint8_t base_address = 0x50; // base address

	// device type
	static constexpr uint8_t at24c01 = 1;
	static constexpr uint8_t at24c02 = 2;
	static constexpr uint8_t at24c04 = 4;
	static constexpr uint8_t at24c08 = 8;
	static constexpr uint8_t at24c16 = 16;
};




#endif // _FILE_AT24CXX_H_
