/**
 * @file dac8563.h
 * @author Javnson (javnson@zju.edu.cn)
 * @brief
 * @version 0.1
 * @date 2024-09-30
 *
 * @copyright Copyright GMP(c) 2024
 *
 */

// This file is for DAC8563 DAC chip
//
// suitable for the following chips
//  + DAC7562, DAC7563 - 12 bits
//  + DAC8162, DAC8163 - 14 bits
//  + DAC8562, DAC8563 - 16 bits
//

#ifndef _FILE_GMP_EXT_DAC8563_H_
#define _FILE_GMP_EXT_DAC8563_H_

#ifdef __cplusplus
extern "C"
{
#endif

    //////////////////////////////////////////////////////////////////////////
    // Data Input Format for DAC8563
    //

    // 24 bits, 3 bytes per frame
    // bit    | 23-22 | 21-19  |  18-16  |   15-0   |
    // detail |   XX  | CMD[3] | ADDR[3] | DATA[16] |
    //
    // For 14 bits ADC, data is 14 bit and Left aligned.
    // For 12 bits ADC, data is 12 bit and Left aligned.
    //

    //////////////////////////////////////////////////////////////////////////
    // COMMAND & ADDRESS
    //

    // Write and update commands

    /**
     * @brief Write to DAC-A input register
     */
#define DAC8563_CMD_WRITE_DAC_A (0x00)

    /**
     * @brief Write to DAC-B input register
     */
#define DAC8563_CMD_WRITE_DAC_B (0x01)

    /**
     * @brief Write to DAC-A and DAC-B input registers
     */
#define DAC8563_CMD_WRITE_DAC_AB (0x07)

    /**
     * @brief Write to DAC-A input register and update all DACs
     */
#define DAC8563_CMD_WRITE_DAC_A_UPDATE_ALL (0x10)

    /**
     * @brief Write to DAC-B input register and update all DACs
     */
#define DAC8563_CMD_WRITE_DAC_B_UPDATE_ALL (0x11)

    /**
     * @brief Write to DAC-A and DAC-B input registers and update all DACs
     */
#define DAC8563_CMD_WRITE_DAC_AB_UPDATE_ALL (0x17)

    /**
     * @brief Write to DAC-A input register and update DAC-A
     */
#define DAC8563_CMD_WRITE_DAC_A_UPDATE (0x18)

    /**
     * @brief Write to DAC-B input register and update DAC-B
     */
#define DAC8563_CMD_WRITE_DAC_B_UPDATE (0x19)

    /**
     * @brief Write to DAC-A and DAC-B input register and update all DACs
     */
#define DAC8563_CMD_WRITE_DAC_AB_UPDATE (0x1F)

    /**
     * @brief Write to DAC-A input register and update DAC-A
     */
#define DAC8563_CMD_UPDATE_DAC_A (0x08)

    /**
     * @brief Write to DAC-B input register and update DAC-B
     */
#define DAC8563_CMD_UPDATE_DAC_B (0x09)

    /**
     * @brief Write to DAC-A and DAC-B input register and update all DACs
     */
#define DAC8563_CMD_UPDATE_DAC_AB (0x0F)

//////////////////////////////////////////////////////////////////////////
// DAC configurations
//

/**
 * @brief Set Gain of DAC-A & DAC-B
 * The target should be one of DAC8563_CONFIG_GAIN_xxxx
 * Gain: DAC-B gain = 1, DAC-A gain = 1 (power-on default)
 */
#define DAC8563_CMD_SET_GAIN (0x02)

    /**
     * @brief Set Gain of DAC-A & DAC-B
     * 2A2B -> 2 DAC-B gain = 2, DAC-A gain = 2 (default with internal VREF)
     */
#define DAC8563_CONFIG_GAIN_2A2B (0x0000)
#define DAC8563_CONFIG_GAIN_1A2B (0x0001)
#define DAC8563_CONFIG_GAIN_2A1B (0x0002)
#define DAC8563_CONFIG_GAIN_1A1B (0x0003)

/**
 * @brief Power up/down DAC-A or/and DAC-B
 * The target should be one of DAC8563_CONFIG_POWER_ON_DACx to power on the DAC
 * The target should be one of DAC8563_CONFIG_POWER_DOWN_DACx to power down the DAC
 */
#define DAC8563_CMD_POWER_CONFIG (0x20)

    /**
     * @brief Power up DAC-A or/and DAC-B
     * parameters to specify which channel will power up
     */
#define DAC8563_CONFIG_POWER_ON_DACA  (0x0001)
#define DAC8563_CONFIG_POWER_ON_DACB  (0x0002)
#define DAC8563_CONFIG_POWER_ON_DACAB (0x0003)

    /**
     * @brief Power down DAC-A or/and DAC-B with 1 kOhm to GND
     * parameters to specify which channel will power down
     */
#define DAC8563_CONFIG_POWER_DOWN_DACA_1K  (0x0009)
#define DAC8563_CONFIG_POWER_DOWN_DACB_1K  (0x000A)
#define DAC8563_CONFIG_POWER_DOWN_DACAB_1K (0x000B)

    /**
     * @brief Power down DAC-A or/and DAC-B with 100 kOhm to GND
     * parameters to specify which channel will power down
     */
#define DAC8563_CONFIG_POWER_DOWN_DACA_100K  (0x0011)
#define DAC8563_CONFIG_POWER_DOWN_DACB_100K  (0x0012)
#define DAC8563_CONFIG_POWER_DOWN_DACAB_100K (0x0013)

    /**
     * @brief Power down DAC-A or/and DAC-B with Hi-Z to GND
     * parameters to specify which channel will power down
     */
#define DAC8563_CONFIG_POWER_DOWN_DACA  (0x0019)
#define DAC8563_CONFIG_POWER_DOWN_DACB  (0x001A)
#define DAC8563_CONFIG_POWER_DOWN_DACAB (0x001B)


/**
 * @brief Reset Command
 * parameters should be one of DAC8563_CONFIG_RESET_x
 */
#define DAC8563_CMD_RESET               (0x28)

    /**
     * @brief Reset DAC-A and DAC-B input register and update all DACs
     */
#define DAC8563_CONFIG_RESET_ONLY_INPUT (0x0000) 

    /**
     * @brief Reset all registers and update all DACs (Power-on-reset update)
     */
#define DAC8563_CONFIG_RESET_ALL        (0x0001)


/**
 * @brief Set LDAC pin utilities
 * parameters should be one of DAC8563_CONFIG_LDAC_x
 */
#define DAC8563_CMD_SET_LDAC_PIN        (0x30)

    /**
     * @brief LDAC pin active for DAC-B and DAC-A
     */
#define DAC8563_CONFIG_LDAC_AB (0x0000)

    /**
     * @brief LDAC pin active for DAC-B and DAC-A
     */
#define DAC8563_CONFIG_LDAC_B (0x0001)

    /**
     * @brief LDAC pin active for DAC-B and DAC-A
     */
#define DAC8563_CONFIG_LDAC_A (0x0002)

    /**
     * @brief LDAC pin active for DAC-B and DAC-A
     */
#define DAC8563_CONFIG_LDAC_NULL (0x0003)


/**
 * @brief Enable internal reference or disable internal reference 
 * parameters should be one of DAC8563_CONFIG_INREF_x
 */
#define DAC8563_CMD_SET_INTERNAL_REF        (0x38)

    /**
     * @brief Disable internal reference and reset DACs to gain = 1
     */
#define DAC8563_CONFIG_INREF_DISABLE (0x0000)

    /**
     * @brief Enable internal reference and reset DACs to gain = 2
     */
#define DAC8563_CONFIG_INREF_ENABLE  (0x0001)

typedef struct _tag_dac8563_t
{
        /**
         * @brief SPI interface which is attached to ADS8688
         */
        spi_halt *spi;

        /**
         * @brief nCS (Chip Select) GPIO interface
         */
        gpio_halt *ncs;

        /**
         * @brief half duplex interface.
         */
        half_duplex_ift msg;

        /**
         * @brief send buffer
         */
         data_gt msg_buffer[3];




}dac_dac8563_t;

/**
 * @brief 
 * 
 * @param dac 
 * @param hspi 
 * @param ncs 
 */
void gmpe_init_dac_dac8563(dac_dac8563_t* dac, spi_halt *hspi, gpio_halt *ncs)
{
    dac->msg.buf = dac->msg_buffer;
    dac->msg.length = 3;
    dac->msg.capacity = 3;
    
    memset(msg_buffer, 3, 0);

    dac->ncs = ncs;
    dac->spi = hspi;
}

/**
 * @brief default command is `DAC8563_CMD_WRITE_DAC_A_UPDATE_ALL`
 * 
 * @param dac 
 * @param target 
 */
void gmpe_dac8563_set_channelA(dac_dac8563_t* dac, uint16_t target)
{

}

/**
 * @brief default command is `DAC8563_CMD_WRITE_DAC_B_UPDATE_ALL`
 * 
 * @param dac 
 * @param target 
 */
void gmpe_dac8563_set_channelB(dac_dac8563_t* dac, uint16_t target)
{

}

/**
 * @brief Write a DAC write command.
 * 
 * @param dac 
 * @param target 
 */
void gmpe_dac8563_send_write_command(dac_dac8563_t* dac, uint16_t target)
{

}

/**
 * @brief Send a update command.
 * `DAC8563_CMD_UPDATE_DAC_AB`
 * 
 * @param dac 
 */
void gmpe_dac8563_update(dac_dac8563_t* dac)
{

}

/**
 * @brief Send a poweron command to DAC
 * 
 * @param dac 
 * @param poweron_cmd 
 */
void gmpe_dac8563_poweron(dac_dac8563_t* dac, uint16_t poweron_cmd)
{

}

/**
 * @brief Power on dual DAC channel, DAC8563_CONFIG_POWER_ON_DACAB
 * 
 * @param dac dac handle.
 */
void gmpe_dac8563_poweron_all(dac_dac8563_t* dac)
{

}



#ifndef DAC8563_SPI_INTERFACE
#define DAC8563_SPI_INTERFACE
#define DAC8563_INTERFACE_TYPE    spi_handle_t
#define DAC8563_INTERFACE_TX_FUNC spi_tx_direct

#endif // DAC8563_SPI_INTERFACE

// command mapping
#define DAC8563_WRITE_REG                ((0x00 << (3 + 16)))
#define DAC8563_SW_LOAD                  ((0x01 << (3 + 16)))
#define DAC8563_WRITE_REG_AND_UPDATE_ALL ((0x02 << (3 + 16)))
#define DAC8563_WRITE_REG_AND_UPDATE     ((0x03 << (3 + 16)))
#define DAC8563_SET_DAC_POWER            ((0x04 << (3 + 16)))
#define DAC8563_SW_RESET                 ((0x05 << (3 + 16)))
#define DAC8563_SET_LDAC                 ((0x06 << (3 + 16)))
#define DAC8563_ENABLE_INNER_REF         ((0x07 << (3 + 16)))

// channel mapping
#define DAC8563_CHANNEL_A       ((0x00 << 16))
#define DAC8563_CHANNEL_B       ((0x01 << 16))
#define DAC8563_CHANNEL_A_AND_B ((0x07 << 16))

    // DAC8563 State machine
    typedef enum _tag_dac8563_sm
    {
        DAC8563_POWERDOWN = 0,
        DAC8563_CONFIG = 1,
        DAC8563_POWERON = 2
    } dac8563_sm_t;

    typedef struct _tag_dac8563
    {
        dac8563_sm_t state;

        // interface, spi port
        DAC8563_INTERFACE_TYPE *_if;

        // Optional, active low, clear all inputs
        // This sets the DAC output voltages accordingly.
        // The device exits clear code mode on the 24th falling edge of the next write to the device.
        hgpio_gt clear;

        // Optional, active low, load DAC data
        // In synchronous mode, keep low. The DAC data may update after 24th sclk cycle.
        // In asynchronous mode, used as a negative edge-triggered timing signal for simultaneous DAC updates.
        //   two channel of DAC may synchronous active.
        hgpio_gt ldac;

        // Sync port is chip select port which was set in `_if`

        // A output buffer of SPI data buffer.
        uint32_t spi_data_buf;

    } dac8563_t;

    /////////////////////////////////////////////
    // set channel

    // Set channel data
    void dac8563_set_channel_data(dac8563_t *handle, uint32_t target_channel, uint16_t data);

    // Set channal data & update all
    void dac8563_set_channel_data_update_all(dac8563_t *handle, uint32_t target_channel, uint16_t data);

    // Set channal data & update
    void dac8563_set_channel_data_update(dac8563_t *handle, uint32_t target_channel, uint16_t data);

    // default setup function
    void dac8563_default_setup(dac8563_t *handle);

// Reset options
// only reset DAC registers & Input registers
#define DAC8563_DATA_ONLY ((0x00))
// reet all DAC registers.
#define DAC8563_RESET_ALL ((0x01))

    // This function will reset the DAC chip
    void dac8563_reset(dac8563_t *handle);

// LDAC control
#define DAC8563_LDAC_DISABLE    ((0x00))
#define DAC8563_LDAC_ACTIVE_B   ((0x01))
#define DAC8563_LDAC_ACTIVE_A   ((0x02))
#define DAC8563_LDAC_ACTIVE_A_B ((0x03))
    // LDAC Pin configuratioin
    void dac8563_cfg_ldac(dac8563_t *handle, uint16_t ldac_command);

// internal reference
#define DAC8563_ENABLE_INTERNAL_REF  ((0x01)) // enable internal reference & gain = 2
#define DAC8563_DISABLE_INTERNAL_REF ((0x00)) // disable internal reference & gain = 1
    // set internal reference if enable
    void dac8563_cfg_internal_ref(dac8563_t *handle, uint16_t internal_ref);

// Gain configuratioin address
#define DAC8563_GAIN ((0x02 << 16)) // do not refresh
// gain configuration
#define DAC8563_GAIN_B2_A2 ((0x00))
#define DAC8563_GAIN_B2_A1 ((0x01))
#define DAC8563_GAIN_B1_A2 ((0x02))
#define DAC8563_GAIN_B1_A1 ((0x03))
    // set DAC gain
    void dac8563_cfg_gain(dac8563_t *handle, uint16_t gain_cfg);

// Power Control
#define DAC8563_POWER_NORMAL             ((0x00 << 3))
#define DAC8563_POWER_DOWN_PULLDOWN_1K   ((0x01 << 3))
#define DAC8563_POWER_DOWN_PULLDOWN_100K ((0x02 << 3))
#define DAC8563_POWER_DOWN_PULLDOWN_HiZ  ((0x03 << 3))

    // This function will send a power control command
    // you should select one of power control macros
    void dac8563_cfg_power(dac8563_t *handle, uint32_t power_command, uint32_t target_channel);

    //
    //
    //// Please disable the NSS port of the
    // class dac8563
    //	:spi_register_device_t
    //{
    // public:
    //	// ctor & dtor
    //	dac8563(gmp_spi_entity* spi,
    //		gmp_gpio_entity* clr,
    //		gmp_gpio_entity* load,
    //		gmp_gpio_entity* sync)
    //		:spi_register_device_t(spi),
    //		clr(clr), sync(sync), load(load)
    //	{}
    //
    //
    // public:
    //	void write_channel_1(uint16_t data)
    //	{
    //		//		sync->set();
    //				// 		ch1_data = data;
    //		ch1_data = ((data & 0xFF) << 8) | ((data & 0xFF00) >> 8);
    //
    //
    //		//		for (int i = 0; i < 10000; ++i);
    //		sync->clear();
    //
    //		write(reg_addr_ch1_data, (data_gt*)&ch1_data, 2);
    //
    //		load->clear();
    //		for (int i = 0; i < 10000; ++i);
    //		load->set();
    //
    //// 		uint16_t command = 0;
    //// 		write(0x0F, (data_gt*)&command, 2);
    //
    //		sync->set();
    //	}
    //
    //	void write_channel_2(uint16_t data)
    //	{
    //		//		sync->set();
    //		// 		ch2_data = data;
    //		ch2_data = ((data & 0xFF) << 8) | ((data & 0xFF00) >> 8);
    //
    //
    //		//		for (int i = 0; i < 10000; ++i);
    //		sync->clear();
    //
    //		write(reg_addr_ch2_data, (data_gt*)&ch2_data, 2);
    //
    //		load->clear();
    //		for (int i = 0; i < 10000; ++i);
    //		load->set();
    //
    //// 		uint16_t command = 0;
    //// 		write(0x0F, (data_gt*)&command, 2);
    //
    //
    //		sync->set();
    //	}
    //
    //	void write_dual_channel(uint16_t data1, uint16_t data2)
    //	{
    //		//		ch1_data = data1;
    //		ch1_data = ((data1 & 0xFF) << 8) | ((data1 & 0xFF00) >> 8);
    //		// 		ch2_data = data2;
    //		ch2_data = ((data2 & 0xFF) << 8) | ((data2 & 0xFF00) >> 8);
    //
    //
    //		for (int i = 0; i < 10000; ++i);
    //		sync->clear();
    //
    //		write(reg_addr_ch1_data, (data_gt*)&ch1_data, 2);
    //		write(reg_addr_ch2_data, (data_gt*)&ch2_data, 2);
    //
    //		load->clear();
    //		for (int i = 0; i < 10000; ++i);
    //		load->set();
    //
    //// 		uint16_t command = 0;
    //// 		write(0x0F, (data_gt*)&command, 2);
    //
    //		sync->set();
    //	}
    //
    //	void clear()
    //	{
    //		clr->clear();
    //		for (int i = 0; i < 10000; ++i);
    //		clr->set();
    //		for (int i = 0; i < 10000; ++i);
    //		clr->clear();
    //
    //		sync->set();
    //
    //	}
    //
    //	void setup()
    //	{
    //		load->set();
    //
    //		sync->clear();
    //
    //		uint16_t command = 0x0100;
    //		write(0x28, (data_gt*)&command, 2);
    //		command = 0x0300;
    //		write(0x20, (data_gt*)&command, 2);
    //		command = 0x0000;
    //		write(0x30, (data_gt*)&command, 2); // Enable LD
    //		command = 0x0100;
    //		write(0x38, (data_gt*)&command, 2);
    //
    //
    //		// 		uint16_t command = 0x0100;
    //		// 		write(0x28, (data_gt*)&command, 2);
    //		// 		command = 0x0300;
    //		// 		write(0x20, (data_gt*)&command, 2);
    //		// 		command = 0x0300;
    //		// 		write(0x30, (data_gt*)&command, 2); // Enable LD
    //		// 		command = 0x0100;
    //		// 		write(0x38, (data_gt*)&command, 2);
    //
    //		//		sync->set();
    //
    //		// 		load->clear();
    //		//
    //		//
    //		// 		ch1_data = 0xFFFF;
    //		//
    //		// 		write(reg_addr_ch1_data, (data_gt*)&ch1_data, 2);
    //		//
    //		// 		for (int i = 0; i < 10000; ++i);
    //		//		load->set();
    //
    //		// 		command = 0;
    //		// 		write(0x0F, (data_gt*)&command, 2);
    //
    //
    //		sync->set();
    //
    //	}
    //
    // protected:
    //	gmp_gpio_entity* clr;
    //	gmp_gpio_entity* load;
    //	gmp_gpio_entity* sync;  // Chip Select
    //
    // public:
    //	uint32_t ch1_data;
    //	uint32_t ch2_data;
    //
    // public:
    //	static constexpr addr_type reg_addr_ch1_data = 0x18;
    //	static constexpr addr_type reg_addr_ch2_data = 0x19;
    //};

#ifdef __cplusplus
}
#endif

#endif // _FILE_DAC8563_H_
