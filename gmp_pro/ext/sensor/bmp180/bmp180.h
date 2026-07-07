/**
 * @file bmp180.h
 * @author Javnson (javnson@zju.edu.cn)
 * @brief 
 * @version 0.1
 * @date 2024-09-30
 * 
 * @copyright Copyright GMP(c) 2024
 * 
 */

#include <core/dev/device_prototype.hpp>


#ifndef _FILE_BMP180_H_
#define _FILE_BMP180_H_

class bmp180
	:public iic_register_device_t
{
public:
	bmp180(gmp_iic_entity* iic)
		:iic_register_device_t(iic, device_addr, 1)
	{}

public:
	void setup()
	{
		// valid device

		// read parameters

	}

protected:
	// calibration param
	int16_t AC1;
	int16_t AC2;
	int16_t AC3;
	uint16_t AC4;
	uint16_t AC5;
	uint16_t AC6;
	int16_t B1;
	int16_t B2;
	int16_t MB;
	int16_t MC;
	int16_t MD;


public:
	static constexpr addr_gt device_addr = 0b1110111;


	static constexpr data_gt device_id = 0x55;


};

#endif
