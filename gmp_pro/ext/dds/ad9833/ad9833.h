/**
 * @file ad9833.h
 * @author Javnson (javnson@zju.edu.cn)
 * @brief
 * @version 0.1
 * @date 2024-09-30
 *
 * @copyright Copyright GMP(c) 2024
 *
 */

#ifndef _FILE_GMP_EXT_AD9833_H_
#define _FILE_GMP_EXT_AD9833_H_

#ifdef __cplusplus
extern "C"
{
#endif

	// register address
#define AD9833_REG_CTRL     ((0x00 << 12))
#define AD9833_REG_FREQ0    ((0x40 << 12))
#define AD9833_REG_FREQ1    ((0x80 << 12))
#define AD9833_REG_PHASE0   ((0xC0 << 12))
#define AD9833_REG_PHASE1   ((0xE0 << 12))

	// predefined commands
#define AD9833_CMD_SET_FREQ0 ((0x2000))

#define AD9833_CMD_RESET     ((0x0100))
#define AD9833_CMD_WRITE     ((0x2100))

	typedef struct _tag_ad9833_ctrl_reg
	{
		// keep 0
		uint16_t reserve0 : 1;

		// This bit (MODE) is used in association with OPBITEN (D5). 
		// The function of this bit is to control what is output at the VOUT pin when the on - chip DAC is connected to VOUT.
		// This bit should be set to 0 if the control bit OPBITEN = 1.
		// MODE = 1, the SIN ROM is bypassed, resulting in a triangle output from the DAC.
		// MODE = 0, the SIN ROM is used to convert the phase information into amplitude information, which results in a sinusoidal signal at the output.
		uint16_t mode : 1;

		// keep 0
		uint16_t reserve2 : 1;

		// This bit (DIV2) is used in association with D5 (OPBITEN).
		// DIV2 = 1, the MSB of the DAC data is passed directly to the VOUT pin.
		// DIV2 = 0, the MSB/2 of the DAC data is output at the VOUT pin.
		uint16_t div2 : 1;

		// keep 0
		uint16_t reserve4 : 1;

		// The function of this bit, in association with D1 (MODE), is to control what is output at the VOUT pin.
		// OPBITEN = 1, the output of the DAC is no longer available at the VOUT pin. 
		//              Instead, the MSB (or MSB / 2) of the DAC data is connected to the VOUT pin.This is useful as a coarse clock source.
		//              The bit DIV2 controls whether it is the MSB or MSB / 2 that is output.
		// OPBITEN = 0, the DAC is connected to VOUT. The MODE bit determines whether it is a sinusoidal or a ramp output that is available.
		uint16_t opbiten : 1;

		// SLEEP12 = 1, powers down the on-chip DAC. 
		//              This is useful when the AD9833 is used to output the MSB of the DAC data.
		// SLEEP12 = 0, implies that the DAC is active.
		uint16_t sleep12 : 1;

		// SLEEP1 = 1, the internal MCLK clock is disabled, the DAC output will remain at its present value as the NCO is no longer accumulating.
		// SLEEP1 = 0, MCLK is enabled.
		uint16_t sleep1 : 1;

		// RESET = 1 resets internal registers to 0, which corresponds to an analog output of midscale.
		// RESET = 0 disables RESET.
		uint16_t reset : 1;

		// keep 0
		uint16_t reserve9 : 1;

		// The PSELECT bit defines whether the PHASE0 register or the PHASE1 register data is added to the output of the phase accumulator.
		uint16_t pselect : 1;

		// The FSELECT bit defines whether the FREQ0 register or the FREQ1 register is used in the phase accumulator.
		uint16_t fselect : 1;

		// This control bit allows the user to continuously load the MSBs or LSBs of a frequency register while ignoring the remaining 14 bits.
		// This is useful if the complete 28-bit resolution is not required. HLB is used in conjunction with D13(B28).
		// This control bit indicates whether the 14 bits being loaded are being transferred to the 14 MSBs or 14 LSBs of the addressed frequency register.
		// D13 (B28) must be set to 0 to be able to change the MSBs and LSBs of a frequency word separately.When D13(B28) = 1, this control bit is ignored.
		// HLB = 1, allows a write to the 14 MSBs of the addressed frequency register.
		// HLB = 0, allows a write to the 14 LSBs of the addressed frequency register.
		uint16_t hlb : 1;

		// Two write operations are required to load a complete word into either of the frequency registers.
		// The first write contains the 14 LSBs of the frequency word, and the next write will contain the 14 MSBs.
		// The first two bits of each 16 - bit word define the frequency register to which the word is loaded and should, therefore, be the same for both of the consecutive writes.
		// The write to the frequency register occurs after both words have been loaded, so the register never holds an intermediate value.
		// B28 = 0, the 28-bit frequency register operates as two 14-bit registers, one containing the 14 MSBs and the other containing the 14 LSBs.
		// This means that the 14 MSBs of the frequency word can be altered independent of the 14 LSBs, and vice versa.
		// To alter the 14 MSBs or the 14 LSBs, a single write is made to the appropriate frequency address.
		// The control bit D12(HLB) informs the AD9833 whether the bits to be altered are the 14 MSBs or 14 LSBs.
		uint16_t b28 : 1;

		// keep 0
		uint16_t reserve14 : 1;

		// keep 0
		uint16_t reserve15 : 1;
	}dds_ad9833_ctrl_reg_t;

	typedef struct _tag_dds_ad9833
	{
		/**
		 * @brief SPI interface which is attached to AD9833
		 */
		spi_halt spi;

		/**
		 * @brief nCS (Chip Select) GPIO interface
		 * nCS pin is named as FSYNC.
		 */
		gpio_halt* ncs;

		/**
		 * @brief This is the SPI message
		 */
		half_duplex_ift spi_msg;

		/**
		 * @brief transmit buffer.
		 */
		uint16_t data_buf;
	}dds_ad9833_t;


#define AD9833_CHANNEL1 0x00
#define AD9833_CHANNEL2 0x01

	void gmpe_init_ad9833(dds_ad9833_t* dds, spi_halt* spi, gpio_halt* ncs)
	{
		dds->spi = spi;
		dds->ncs = ncs;
		dds->data_buf = 0;

		dds->spi_msg.buf = &dds->data_buf;
		dds->spi_msg.capacity = 2;
		dds->spi_msg.capacity = 2;
	}

	void gmpe_ad9833_set_param(dds_ad9833_t* dds, uint32_t freq, fast_gt freq_sfr, fast_gt waveform, uint32_t phase)
	{
		dds_ad9833_ctrl_reg_t ctrl_reg;

		uint16_t freq_lsb = freq & 0x3FFF;
		uint16_t freq_msb = (freq >> 14) & 0x3FFF;

		uint32_t phase_data = phase | 0xC000;
		
		ctrl_reg.reset = 1;

		dds->data_buf = 

		gmp_hal_spi_send(dds->spi, &dds->spi_msg);

		AD9833_Write(0x0100);
	}

	// handle: ad9833 object
	// channel : AD9833_CHANNEL1 or AD9833_CHANNEL2
	// freq0: target frequency
	void ad9833_write_freq(ad9833_t* handle, uint32_t channel, uint32_t freq0);



	// handle: ad9833 object
	// channel: AD9833_CHANNEL1 or AD9833_CHANNEL2
	// phase: target phase
	void ad9833_write_phase(ad9833_t* handle, uint32_t channel, uint32_t phase);



	// Four standard waveform
#define AD9833_SINUSOID_WAVE 0x00
#define AD9833_TRIANGLE_WAVE 0x01
#define AD9833_MSB_DIV2      0x02
#define AD9833_MSB           0x03

	void ad9833_set_waveform(ad9833_t* handle, fast_gt wave);


	// config internal reference clock
	// enable: 1: disable the internal clock
	//         0: enable the internal clock
	void ad9833_cfg_internal_clk(ad9833_t* handle, fast_gt enable);


#ifdef __cplusplus
}
#endif

#endif // _FILE_GMP_EXT_AD9833_H_
