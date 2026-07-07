
#ifndef _FILE_DAC8554_H_
#define _FILE_DAC8554_H_

#ifdef __cplusplus
extern "C"
{
#endif // __cplusplus

    // DAC8554 Message structure
    // | 7  | 6  | 5   | 4   | 3 | 2        | 1        | 0   |
    // | 23 | 22 | 21  | 20  |19 | 18       | 17       |16   | 15 - 0 |
    // | A1 | A0 | LD1 | LD0 | X | DAC SEL1 | DAC SEL0 | PD0 |   SR   |
    //
    // A1 A0 should correspond to the package address set via pin 13 and pin 14
    //
    // LD1 LD0 determine the load command
    //  + LD1 LD0 = 00 : Single channel store
    //    the target channel determined by DAC SEL1 and DAC SEL0 bits.
    //    The temporary register (data buffer) is updated with SR data.
    //  + LD1 LD0 = 01 : single channel update
    //    the target channel determined by DAC SEL1 and DAC SEL0 bits.
    //    The temporary register (Data buffer) and DAC reg is updated with ST data.
    //  + LD1 LD0 = 10 : Simultaneous update
    //    the target channel which was selected by DAC SEL1 and DAC SEL0 bits will update
    //    with SR data. Meanwhile, all the other channels get updated with previous stored data.
    //  + LD1 LD0 = 11 ; Broadcast update
    //    All the DAC8554s on the SPI bus respond, regardless of address matching.
    //    if DB18(DAC_SEL1) = 1 , then SR data will ignored, all channels will get updated
    //    with previously stored data.
    //    if DB18(DAC_SEL1) = 0 , then SR data updates all channels in the system.
    //    This broadcast updated feature allows the simultaneous update of up to 16 channels.
    // X Don't care.
    //    In this library this bit will permanently equal to 0.
    // DAC SEL1 and DAC SEL2
    //    
    // PD0 power down flag
    //    when this flag is set, then DB15 and DB14 is used to select power-down mode.
    //    at this time, SR[15] and SR[14] no longer present the two MSB data.
    //    Note: Similar to data, power down conditions can be stored at the 
    //      temporary registers of each DAC.
    // 
    //    + DB15 DB14 = 00 output high impedance
    //    + DB15 DB14 = 01 output typically 1kOhm to GND
    //    + DB15 DB14 = 10 output typically 100kOhm to GND
    //    + DB15 DB14 = 11 output high impedance
    //
    // SPI bus requirement, mode 0
    // CPOL = 0 (negative edge is active),  
    // CPHA = 0
    //
    // Chip physical joint
    // nSYNC serves as nCS in SPI bus.
    // nEnable for normal operation this pin must be tied to a logic low.
    //         the DAC8554 stops listening to the serial port.
    // LDAC for synchronous mode LDAC should connected to GND permanently.
    //      for asynchronous mode, LDAC pin is used as a positive edge triggered timing signal.
    //


#define DAC8554_LDCMD_SINGLE_CH_STORE     ((0<<4))
#define DAC8554_LDCMD_SINGLE_CH_UPDATE    ((1<<4))
#define DAC8554_LDCMD_SIMULTANEOUS_UPDATE ((2<<4))
#define DAC8554_LDCMD_BROADCAST_UPDATE    ((3<<4))

#define DAC8554_CHANNEL_A                 ((0<<1))
#define DAC8554_CHANNEL_B                 ((1<<1))
#define DAC8554_CHANNEL_C                 ((2<<1))
#define DAC8554_CHANNEL_D                 ((3<<1))

#define DAC8554_DISABLE_POWERDOWN         ((0))
#define DAC8554_ENABLE_POWERDOWN          ((1))

#define DAC8554_PWMODE_HIGHIMPL           ((0))
#define DAC8554_PWMODE_1KGND              ((1))
#define DAC8554_PWMODE_100KGND            ((2))

// ADDR in [0,3], phsical address for DAC
// LD_MODE select from DAC8554_LDCMD
// CHANNEL_SEL select form DAC8554_CHANNEL
#define MAKE_DAC8554_CMD(ADDR, LD_MODE, CHANNEL_SEL, PD0) \
        ((ADDR) | (LD_MODE) | (CHANNEL_SEL) | (PD0))

    typedef struct _tag_dac8554_t
    {
        spi_halt spi_if;

        gpio_halt ncs;

        gpio_halt enable;

        gpio_halt ldac;
    }dac8554_t;

#ifdef __cplusplus
}
#endif // __cplusplus

#endif // _FILE_DAC8554_H_
