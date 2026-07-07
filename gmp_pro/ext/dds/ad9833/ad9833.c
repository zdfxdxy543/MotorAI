/**
 * @file ad9833.c
 * @author Javnson (javnson@zju.edu.cn)
 * @brief 
 * @version 0.1
 * @date 2024-09-30
 * 
 * @copyright Copyright GMP(c) 2024
 * 
 */
 
#include <core/gmp_core.h>

#include "ad9833.h"



void ad9833_write_freq(ad9833_t* handle, uint32_t channel, uint32_t freq0)
{
	uint32_t channel_mask = 0;
	handle->ctrl.b28 = 1;

	if (channel == AD9833_CHANNEL1)
		channel_mask = AD9833_REG_FREQ0;
	else if (channel == AD9833_CHANNEL2)
		channel_mask = AD9833_REG_FREQ1;
	else
		return;


	// sync ctrl register, prepare for continuous writing
	// in order to transfer reg struct to a uint16_t 
	handle->data_buf = BE16((uint16_t)AD9833_REG_CTRL | *(uint16_t*)&handle->ctrl);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->data_buf), 2);

	// LSB
	handle->data_buf = BE16(channel_mask | (freq0 & 0x3FFF));
	spi_tx_direct(handle->_if, ((data_gt*)&handle->data_buf), 2);

	// MSB
	handle->data_buf = BE16(channel_mask | (freq0 & 0x0FFFC000));
	spi_tx_direct(handle->_if, ((data_gt*)&handle->data_buf), 2);

	// close continous writing
	handle->ctrl.b28 = 0;

}


void ad9833_write_phase(ad9833_t* handle, uint32_t channel, uint32_t phase)
{
	uint32_t channel_mask = 0;

	if (channel == AD9833_CHANNEL1)
		channel_mask = AD9833_REG_PHASE0;
	else if (channel == AD9833_CHANNEL2)
		channel_mask = AD9833_REG_PHASE1;
	else
		return;

	handle->data_buf = BE16(channel_mask | (phase & 0x0FFF));
	spi_tx_direct(handle->_if, ((data_gt*)&handle->data_buf), 2);

}


void ad9833_set_waveform(ad9833_t* handle, fast_gt wave)
{
	// set waveform 
	switch (wave)
	{
	case AD9833_SINUSOID_WAVE:
		handle->ctrl.opbiten = 0;
		handle->ctrl.mode = 0;
		// start DAC
		handle->ctrl.sleep12 = 0;
		break;
	case AD9833_TRIANGLE_WAVE:
		handle->ctrl.opbiten = 0;
		handle->ctrl.mode = 1;
		// start DAC
		handle->ctrl.sleep12 = 0;
		break;
	case AD9833_MSB_DIV2:
		handle->ctrl.opbiten = 1;
		handle->ctrl.mode = 0;
		handle->ctrl.div2 = 0;
		// DAC Power Down
		handle->ctrl.sleep12 = 1;
		break;
	case AD9833_MSB:
		handle->ctrl.opbiten = 1;
		handle->ctrl.mode = 0;
		handle->ctrl.div2 = 1;
		// DAC Power Down
		handle->ctrl.sleep12 = 1;
		break;
	}

	// sync ctrl register
	handle->data_buf = BE16((uint16_t)AD9833_REG_CTRL | *(uint16_t*)&handle->ctrl);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->data_buf), 2);

	return;

}


void ad9833_cfg_internal_clk(ad9833_t* handle, fast_gt enable)
{
	handle->ctrl.sleep1 = enable;
	
	// write control register to ad9833
	handle->data_buf = BE16((uint16_t)AD9833_REG_CTRL | *(uint16_t*)&handle->ctrl);
	spi_tx_direct(handle->_if, ((data_gt*)&handle->data_buf), 2);
}

