/**
 * @file ads8688.h
 * @author Javnson (javnson@zju.edu.cn)
 * @brief
 * @version 0.1
 * @date 2024-09-30
 *
 * @copyright Copyright GMP(c) 2024
 *
 */

// Reference Config
// Data Size: 8
// BaudRate: 10.5 MHz
// CPOL: Low
// CPHA: 2 Edge


#ifndef _FILE_GMP_EXT_ADS8688_H_
#define _FILE_GMP_EXT_ADS8688_H_

#ifdef __cplusplus
extern "C"
{
#endif // __cplusplus

//////////////////////////////////////////////////////////////////////////
// Command List
//
// Data Acquisition Timing (Shotting mode)
// PIN | CS (H) | COMMAND SECTION (31:16) | Sample Result (15:0) | CS (H) |
// NCS |    1   |                        0000                    |   1    |
// SDI |  XXXX  |  ADS8688_CMD_MANUAL_CHx |          XXXX        |   1    |
//                  (Sample command N+1)
// SDO |  XXXX  |            XXXX         |  Data from sample N  |   1    |
//              ^ * Here is the Sample trigger point for N
//
// PIN          | COMMAND SECTION (31:16) | Sample Result (15:0) | CS (H) |
// NCS          |                        0000                    |   1    |
// SDI          |  ADS8688_CMD_MANUAL_CHx |          XXXX        |   1    |
//                  (Sample command N+2)
// SDO          |            XXXX         | Data from sample N+1 |   1    |
//              ^ * Here is the Sample trigger point for N+1
//
//
// Continuous Data Acquisition Timing (Auto RST mode)
// Reference Fig. 82 Device Operation Example in AUTO_RST Mode
// PIN | nul | CMD | Result | nul | CMD | Result | nul | CMD | Result | nul | CMD | Result | nul | CMD | Result | nul |
// NCS |  1  |  0  |    0   |  1  |  0  |    0   |  1  |  0  |    0   |  1  |  0  |    0   |  1  |  0  |    0   |  1  |
// SDI |  1  | RST |    X   |  1  | 000 |    X   |  1  | 000 |    X   |  1  | RST |    X   |  1  | 000 |    X   |  1  |
// SDO |  1  |  X  |  Res N |  1  |  X  |   Ch0  |  1  |  X  |   Ch1  |  1  |  X  |   Ch2  |  1  |  X  |   Ch0  |  1  |
//           ^ * Trigger N        ^ * Trigger N+1(CH0) ^ * Trigger N+2(CH1) ^ * Trigger N+3(CH2) ^ * Trigger N+4(CH0)
//
//
// Enter or Remain STANDBY/POWERDOWN mode
// PIN | CS (H) | COMMAND SECTION (31:16) | Sample Result (15:0) | CS (H) |
// NCS |    1   |                        0000                    |   1    |
// SDI |  XXXX  | Stand by Mode(0x8200)   |          XXXX        |   1    |
//                Power down Mode(0x8300) |
// SDO |  XXXX  |            XXXX         |  Data from sample N  |   1    |
//              ^ * Here is the Sample trigger point
//                  Enter STANDBY mode or Keep in STANDBY mode * ^
//
// Exit STANDBY mode
// PIN | CS (H)  | Command Section (15:0) | CS (H) |
// NCS |    1    |           0000         |   1    |
// SDI |  XXXX   |    AUTO_RST/MAN_CHn    |   1    |
// SDO |  XXXX   |           0000         |   1    |
//            Leave StandBY mode need 20us,   ^
//            Leave PowerDown mode need 15ms  |
// So the CS should keep high for a little while
//

/**
 * @brief Command: Continue operation in previous mode
 */
#define ADS8688_CMD_CONTINUE_OPERATION (0x0000)

/**
 * @brief Command: Device is placed into standby mode
 */
#define ADS8688_CMD_STANDBY (0x8200)

/**
 * @brief Command: Device is powered down
 */
#define ADS8688_CMD_POWERDOWN (0x8300)

/**
 * @brief Command: Program register is reset to default
 */
#define ADS8688_CMD_RESET_REGS (0x8500)

/**
 * @brief Command: Auto mode enabled following a reset
 */
#define ADS8688_CMD_AUTO_RESET (0xA000)

/**
 * @brief Command: Channel 0 input is selected
 */
#define ADS8688_CMD_MANUAL_CH0 (0xC000)

/**
 * @brief Command: Channel 1 input is selected
 */
#define ADS8688_CMD_MANUAL_CH1 (0xC400)

/**
 * @brief Command: Channel 2 input is selected
 */
#define ADS8688_CMD_MANUAL_CH2 (0xC800)

/**
 * @brief Command: Channel 3 input is selected
 */
#define ADS8688_CMD_MANUAL_CH3 (0xCC00)

/**
 * @brief Command: Channel 4 input is selected
 * This command is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_CMD_MANUAL_CH4 (0xD000)

/**
 * @brief Command: Channel 5 input is selected
 * This command is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_CMD_MANUAL_CH5 (0xD400)

/**
 * @brief Command: Channel 6 input is selected
 * This command is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_CMD_MANUAL_CH6 (0xD800)

/**
 * @brief Command: Channel 7 input is selected
 * This command is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_CMD_MANUAL_CH7 (0xDC00)

/**
 * @brief Command: AUX channel input is selected
 */
#define ADS8688_CMD_MANUAL_CH_AUX (0xE000)

//////////////////////////////////////////////////////////////////////////
// Program Register Map
//
// Register access, Read/Write Operation, MSB
// Each frame has 3 bytes.
//
// Write Operation
// PIN | REG Address [23:17] | WR-/RD [16] | DATA [15:8] | RET Stage [7:0] |
// SDI |        ADDR         |    1 (WR)   |   DIN[7:0]  |      xxxx       |
// SDO |        0000         |      0      |     0000    |    DIN[7:0]     |
//
// Read Operation
// PIN | REG Address [23:17] | WR-/RD [16] | DATA [15:8] | RET Stage [7:0] |
// SDI |        ADDR         |    0 (RD)   |     XXXX    |      xxxx       |
// SDO |        0000         |      0      |     0000    |    DIN[7:0]     |
//
//

/**
 * @brief AUTO SCAN SEQUENCING CONTROL
 * AUTO_SEQ_EN: Enable Sequencing channel
 * Default: 0xFF, all the channels is in sequencing
 */
#define ADS8688_REG_AUTO_SEQ_EN (0x01)

/**
 * @brief AUTO SCAN SEQUENCING CONTROL
 * Channel Power Down
 * Default: 0x00, all the channels is on.
 */
#define ADS8688_REG_CHANNEL_PD (0x02)

/**
 * @brief DEVICE FEATURES SELECTION CONTROL
 * Feature Select, Control Register
 * Default, 0x00
 */
#define ADS8688_REG_CTRL (0x03)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 0 Input Range, CHN0_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 */
#define ADS8688_REG_CHN0_INPUT_RANGE (0x05)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 1 Input Range, CHN1_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 */
#define ADS8688_REG_CHN1_INPUT_RANGE (0x06)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 2 Input Range, CHN0_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 */
#define ADS8688_REG_CHN2_INPUT_RANGE (0x07)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 3 Input Range, CHN1_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 */
#define ADS8688_REG_CHN3_INPUT_RANGE (0x08)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 4 Input Range, CHN0_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 * This register is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_REG_CHN4_INPUT_RANGE (0x09)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 5 Input Range, CHN1_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 * This register is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_REG_CHN5_INPUT_RANGE (0x0A)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 6 Input Range, CHN0_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 * This register is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_REG_CHN6_INPUT_RANGE (0x0B)

/**
 * @brief RANGE SELECT REGISTERS
 * Channel 7 Input Range, CHN1_INPUT_RANGE
 * Default, 0x00, Input range is set to ��2.5 x VREF
 * This register is ADS8688 chip only, ADS8684 is not support.
 */
#define ADS8688_REG_CHN7_INPUT_RANGE (0x0C)

/**
 * @brief COMMAND READ BACK (Read-Only)
 * Command Read Back
 */
#define ADS8688_REG_CMD_RDBK (0x3F)

    //////////////////////////////////////////////////////////////////////////
    // Channel Mask
    // These macros are used to set AUTO SCAN SEQUENCING CONTROL register.
    // They are ADS8688_REG_AUTO_SEQ_EN, ADS8688_REG_CHANNEL_PD.
    //

#define ADS8688_PARAM_CHANNEL_MASK0 ((0x01))
#define ADS8688_PARAM_CHANNEL_MASK1 ((0x02))
#define ADS8688_PARAM_CHANNEL_MASK2 ((0x04))
#define ADS8688_PARAM_CHANNEL_MASK3 ((0x08))
#define ADS8688_PARAM_CHANNEL_MASK4 ((0x10))
#define ADS8688_PARAM_CHANNEL_MASK5 ((0x20))
#define ADS8688_PARAM_CHANNEL_MASK6 ((0x40))
#define ADS8688_PARAM_CHANNEL_MASK7 ((0x80))

    //////////////////////////////////////////////////////////////////////////
    // ADS868X Control Register
    // These macros are used to set DEVICE FEATURES SELECTION CONTROL register.
    // They are ADS8688_REG_CTRL
    //
    // 0-2: SDO data format bits
    // 6-7: Device ID bits
    //

    // SDO mode config
    // Description of Program Register Bits for SDO Data Format
    //
    // SDO MODE |  BIT 24-9  | BIT 8-5  | BIT 4-3 | BIT 2-0         |
    // 000 (0)  | ADC Result |             SDO Pulled LOW           |
    // 001 (1)  | ADC Result | CHN ADDR |       SDO Pulled LOW      |
    // 010 (2)  | ADC Result | CHN ADDR | DEV ADDR | SDO Pulled LOW |
    // 011 (3)  | ADC Result | CHN ADDR | DEV ADDR |  Input Range   |
    //
    //
    // Bit Description for the SDO Data
    //
    // ADC Result  (24- 9): 16 bits of conversion result for the channel represented in MSB-first format.
    //                      16th SCLK falling edge, no latency.
    // CHN ADDR    (8 - 5): Four bits of channel address.
    //                      0-3: Channel 0-3,
    //                      4-7: Channel 4-7, valid only for the ADS8688
    // DEV ADDR    (4 - 3): Two bits of device address (mainly useful in daisy-chain mode).
    // Input Range (2 - 0): Three LSB bits of input voltage range.
    //                      The value of input range reference Range Selection Reg parameter.
    //

#define ADS8688_PARAM_CTRL_SDO_MODE0 ((0x00))
#define ADS8688_PARAM_CTRL_SDO_MODE1 ((0x01))
#define ADS8688_PARAM_CTRL_SDO_MODE2 ((0x02))
#define ADS8688_PARAM_CTRL_SDO_MODE3 ((0x03))

// DEV ID config
// Device ID bits in daisy-chain mode
//

// 00 = ID for device 0 in daisy-chain mode
#define ADS8688_PARAM_CTRL_DEV_ID0 ((0x00))
// 01 = ID for device 1 in daisy-chain mode
#define ADS8688_PARAM_CTRL_DEV_ID1 ((0x40))
// 10 = ID for device 2 in daisy-chain mode
#define ADS8688_PARAM_CTRL_DEV_ID2 ((0x80))
// 11 = ID for device 3 in daisy-chain mode
#define ADS8688_PARAM_CTRL_DEV_ID3 ((0xC0))

    //////////////////////////////////////////////////////////////////////////
    // interface redirection

    // null here

    // user may set SPI handle to null, in order to send duplex message manually.

    /**
     * @brief This is ADS8688 ADS8684 ADC source type.
     */
    typedef struct _tag_ads8688_t
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
         * @brief nRST (Reset) & nPD (Power Done) GPIO interface
         */
        gpio_halt *nrst;

        /**
         * @brief transmit buffer.
         */
        data_gt send_buffer[4];

        /**
         * @brief receive buffer.
         */
        data_gt recv_buffer[4];

        /**
         * @brief This is the SPI message
         */
        duplex_ift spi_msg;

    } adc_ads8688_t;


    /**
     * @brief Reset the ADS8688 device.
     * @param obj object to ADS8688
     * @return gmp_stat_t
     */
    gmp_stat_t gmpe_ads8688_rst(adc_ads8688_t *obj)
    {

        // judge if hardware rst is enable
        if (obj->nrst)
        {
            gmp_hal_gpio_clear(obj->nrst);
            for (int i = 0; i < 5; ++i)
                GMP_INSTRUCTION_NOP;
            gmp_hal_gpio_set(obj->nrst);
        }

        // software reset
        obj->spi_msg.length = 2;
        obj->spi_msg.tx_buf[0] = (ADS8688_CMD_RESET_REGS & 0xFF00) >> 8;
        obj->spi_msg.tx_buf[1] = ADS8688_CMD_RESET_REGS & 0x00FF;

        if (obj->spi)
        {
            if (obj->ncs)
                gmp_hal_gpio_clear(obj->ncs);

            gmp_hal_spi_send_recv(obj->spi, &obj->spi_msg);

            if (obj->ncs)
                gmp_hal_gpio_set(obj->ncs);
        }

        return GMP_STAT_OK;
    }


    /**
     * @brief init a ADS8688 objects
     * @param obj handle to object
     * @param hspi target spi handle, could be nullptr, if user will send these message manually.
     * @param ncs target nCS GPIO handle, could be nullptr.
     * @param nrst target nRST GPIO hanle, could be nullptr.
     * @return gmp_stat_t
     */
    gmp_stat_t gmpe_ads8688_init(adc_ads8688_t *obj, spi_halt *hspi, gpio_halt *ncs, gpio_halt *nrst)
    {
        // init SPI msg item
        obj->spi_msg.capacity = 4;
        obj->spi_msg.length = 0;
        obj->spi_msg.rx_buf = obj->recv_buffer;
        obj->spi_msg.tx_buf = obj->send_buffer;

        // bind SPI driver
        obj->spi = hspi;
        obj->ncs = ncs;
        obj->nrst = nrst;

        // Send SPI msg to init device
        gmpe_ads8688_rst(obj);

            
                gmp_hal_gpio_set(nrst);
        return GMP_STAT_OK;
    }



    /**
     * @brief ADS8688 specify a adc channel to measure.
     *
     * @param obj handle of ADC
     * @param target_channel_cmd ADS8688_CMD_MANUAL_CH0 to ADS8688_CMD_MANUAL_CH8
     * @param result return the last target, could be nullptr if the result could be ignored.
     * @return gmp_stat_t
     */
    gmp_stat_t gmpe_ads8688_request(adc_ads8688_t *obj, uint16_t target_channel_cmd, uint16_t *result)
    {
            //request command
            obj->spi_msg.length = 4;
            
            
        // clear send buffer
        memset(obj->send_buffer, 0, 4);

        // fill command
        obj->send_buffer[0] = (target_channel_cmd & 0xFF00) >> 8;
        obj->send_buffer[1] = target_channel_cmd & 0x00FF;

        // communication stage
        if (obj->spi)
        {
            if (obj->ncs)
                gmp_hal_gpio_clear(obj->ncs);

            gmp_hal_spi_send_recv(obj->spi, &obj->spi_msg);

            if (obj->ncs)
                gmp_hal_gpio_set(obj->ncs);
        }

        // get result
        if (result)
            *result = gmp_l2b16(*((uint16_t *)(obj->recv_buffer + 2)));

        return GMP_STAT_OK;
    }

#ifdef __cplusplus
}
#endif // __cplusplus

#endif // _FILE_GMP_EXT_ADS8688_H_
