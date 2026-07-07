/**
 * @file bmp180.hpp
 * @author Javnson (javnson@zju.edu.cn)
 * @brief 
 * @version 0.1
 * @date 2024-09-30
 * 
 * @copyright Copyright GMP(c) 2024
 * 
 */

#include <core/gmp_core.hpp>

#ifndef _FILE_BMP180_H_
#define _FILE_BMP180_H_

// #define BPM180_REG_PARAM_AC1 (0xAAAB)
// #define BPM180_REG_PARAM_AC2 (0xACAD)
// #define BPM180_REG_PARAM_AC3 (0xAEAF)
// #define BPM180_REG_PARAM_AC4 (0xB0B1)
// #define BPM180_REG_PARAM_AC5 (0xB2B3)
// #define BPM180_REG_PARAM_AC6 (0xB4B5)
// #define BPM180_REG_PARAM_B1 (0xB6B7)
// #define BPM180_REG_PARAM_B2 (0xB8B9)
// #define BPM180_REG_PARAM_MB (0xBABB)
// #define BPM180_REG_PARAM_MC (0xBCBD)
// #define BPM180_REG_PARAM_MD (0xBEBF)

#define BMP180_REG_PARAM_BEGIN (0xAAU)
#define BMP180_REG_PARAM_END (0xBEU)

#define BMP180_REG_CMD (0xF4)
#define BMP180_REG_OUT_XSB (0xF8)
#define BMP180_REG_OUT_LSB (0xF7)
#define BMP180_REG_OUT_MSB (0xF6)

#define BMP180_REG_DEV_ID (0xD0)
#define BMP180_DEV_ID (0x55)

#define BMP180_CMD_START_T (0x2E)
#define BMP180_CMD_START_P(oss) (0x34 + (oss << 6))

#define BMP180_WAITMS_T (4.5f)
#define BMP180_WAITMS_P(oss) (3.0f * ((1 << oss) - 1) + 4.5)

class bmp180
	: public iic_register_device_t
{
public:
	bmp180(gmp_iic_entity *iic)
		: iic_register_device_t(iic, device_addr, 1)
	{}

public:
	// work functions
	/**
	 * This function will firstly get chip-id to verify it works well.
	 *                    Then get calibration param from EEPROM of BMP180.
	 */
	gmp_stat_t init()
	{
		// get chip-id to verify it works well
		if ((this->read(BMP180_REG_DEV_ID)) != BMP180_DEV_ID)
		{
			cali_param.AC6 = 0xEE;
			return GMP_STAT_HARD_ERROR;
		}

		// get calibration param
		for (uint8_t i = 0; i < 11; ++i)
		{
			uint8_t reg_MSB = BMP180_REG_PARAM_BEGIN + i * 2;
			uint8_t reg_LSB = reg_MSB + 1;

			uint8_t MSB = this->read(reg_MSB);
			uint8_t LSB = this->read(reg_LSB);

			((uint16_t *)(&(this->cali_param)))[i] = ((MSB & 0xFF) << 8) | LSB;
		}
		return GMP_STAT_OK;
	}

	/**
	 * This function will check if the convertion is OK.
	 */
	bool is_cplt()
	{
		uint8_t ctrl_meas = this->read(BMP180_REG_CMD);
		if((ctrl_meas & 0b00100000) == 0)
		{
			return true;
		}
		else
		{
			return false;
		}
	}

	/**
	 * This function will send a cmd to BMP180 and start temperature measurement.
	 */
	void start_temp()
	{
		this->send_cmd(BMP180_CMD_START_T);
	}

	/**
	 * This function should be called after is_cplt() to ensure the convertion is OK.
	 * This funciton just get result from BMP180 EEPROM, no matter UT or UP.
	 * @param xsb used to indicate wether XSB of result is on ues.
	 * @retval uncompensated temperature or pressure value.
	 */
	uint32_t get_res(bool xsb = false)
	{
		if(xsb)
		{
			// TODO
		}

		uint8_t MSB = this->read(BMP180_REG_OUT_MSB);
		uint8_t LSB = this->read(BMP180_REG_OUT_LSB);

		this->UT = ((MSB & 0xFF) << 8) | LSB;

		// TODO xsb return
		return ((MSB & 0xFF) << 8) | LSB;
	}

	/**
	 * This function will send a cmd to BMP180 and start pressure measurement according different oss.
	 * @param oss if oss is 0, 1, 2, or 3, pressure measurement will start on this accuracy,
	 *            else, according to this->oss.
	 *            oss is 4 by default.
	 * @note formal parameter oss will NOT change this->oss.
	 */
	void start_pres();

	/**
	 * This function will calculate the true value of temperature and pressure according to a certain algorithm.
	 */
	void calc_value() GMP_NO_OPT
	{
		int32_t X1 = (UT - cali_param.AC6) * cali_param.AC5 >> 15;
		int32_t X2 = (cali_param.MC << 11) / (X1 + cali_param.MD);
		int32_t B5 = X1 + X2;
		this->T = (B5 + 8) >> 4;
	}

private:
	/**
	 * This inline function is used to send start cmd to BMP180.
	 * This inline funciton is called by start_temp() and start_pres().
	 */
	inline void send_cmd(uint8_t cmd)
	{
		this->write(BMP180_REG_CMD, cmd);
	}

public:
	uint32_t get_temperature()
	{
		return this->T;
	}

	uint32_t get_pressure();

public:
	void setup()
	{
		// valid device

		// read parameters
	}

public:
// private:
	// calibration param
	struct
	{
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
	} cali_param;

	// control param
	uint8_t oss;

	// temperature & pressure
	int32_t UT;
	int32_t UP;

	int32_t T;
	int32_t p;

public:
	static constexpr addr_gt device_addr = 0b1110111;

	static constexpr data_gt device_id = 0x55;
};

#endif
