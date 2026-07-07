/**
 * @file dac8563.c
 * @author Javnson (javnson@zju.edu.cn)
 * @brief 
 * @version 0.1
 * @date 2024-09-30
 * 
 * @copyright Copyright GMP(c) 2024
 * 
 */

#include <core/gmp_core.h>
#include "dac8563.h"

void dac8563_default_setup(dac8563_t* handle)
{
	dac8563_reset(handle);

	dac8563_cfg_ldac(handle, DAC8563_LDAC_DISABLE);

	dac8563_cfg_internal_ref(handle, DAC8563_ENABLE_INTERNAL_REF);

	dac8563_cfg_power(handle, DAC8563_POWER_NORMAL, DAC8563_CHANNEL_A_AND_B);

	dac8563_set_channel_data(handle, DAC8563_CHANNEL_A_AND_B, 5);
}


void dac8563_reset(dac8563_t* handle)
{
	// big endian 
	handle->spi_data_buf = BE32(DAC8563_SW_RESET | DAC8563_RESET_ALL);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}


void dac8563_cfg_power(dac8563_t* handle, uint32_t power_command, uint32_t target_channel)
{
	handle->spi_data_buf = BE32(DAC8563_SET_DAC_POWER | power_command | target_channel);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}

void dac8563_cfg_ldac(dac8563_t* handle, uint16_t ldac_command)
{
	handle->spi_data_buf = BE32(DAC8563_SET_LDAC | ldac_command);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}

void dac8563_set_channel_data(dac8563_t* handle, uint32_t target_channel, uint16_t data)
{
	handle->spi_data_buf = BE32(DAC8563_WRITE_REG | target_channel | data);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}

void dac8563_set_channel_data_update_all(dac8563_t* handle, uint32_t target_channel, uint16_t data)
{
	handle->spi_data_buf = BE32(DAC8563_WRITE_REG_AND_UPDATE_ALL | target_channel | data);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}

void dac8563_set_channel_data_update(dac8563_t* handle, uint32_t target_channel, uint16_t data)
{
	handle->spi_data_buf = BE32(DAC8563_WRITE_REG_AND_UPDATE | target_channel | data);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}


void dac8563_cfg_internal_ref(dac8563_t* handle, uint16_t internal_ref)
{
	handle->spi_data_buf = BE32(DAC8563_ENABLE_INNER_REF | internal_ref);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}

void dac8563_cfg_gain(dac8563_t* handle, uint16_t gain_cfg)
{
	handle->spi_data_buf = BE32(DAC8563_WRITE_REG | DAC8563_GAIN | gain_cfg);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->spi_data_buf) + 1, 3);
}
