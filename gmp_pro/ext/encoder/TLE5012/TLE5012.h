/**
 * @file TLE5012.h
 * @author Javnson (javnson@zju.edu.cn)
 * @brief TLE5012 is a half-duplex Motor Encoder.
 *  So the SPI interface should support half duplex function.
 * @version 0.1
 * @date 2024-09-30
 *
 * @copyright Copyright GMP(c) 2024
 *
 */

// This header is for TLE5012 GMR-Based Angle Sensor

#ifndef _FILE_TLE5012_H_
#define _FILE_TLE5012_H_

#include "core/std/default_peripheral.config.h"
#include "core/dev/devif.h"
#include <cstdint>

#define TLE5012_READ_STATUS     0x8000
#define TLE5012_READ_ANGLE      0x8020
#define TLE5012_READ_SPEED      0x8030
#define TLE5012_READ_REVOLUTION 0x8040

typedef struct _tag_tle5012_t
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
     * @brief transmit interface.
     */
    half_duplex_ift tx;

    /**
     * @brief This is the receive interface
     */
    half_duplex_ift rx;

    /**
     * @brief transmit buffer.
     */
    data_gt tx_buffer[4];

    /**
     * @brief receive buffer.
     */
    data_gt rx_buffer[4];

} encoder_tle5012_t;

/**
 * @brief GMP Extension module. initialize a TLE5012 module
 * @param enc encoder handle
 * @param hspi spi handle
 * @param ncs cs pin GPIO handle
 */
void gmpe_init_tle5012_encoder(encoder_tle5012_t *enc, spi_halt *hspi, gpio_halt *ncs)
{
    memset(enc->rx_buffer, 4, 0);
    memset(enc->tx_buffer, 4, 0);

    init_half_duplex_channel(enc->rx, enc->rx_buffer, 4, 4);
    init_half_duplex_channel(enc->tx, enc->tx_buffer, 4, 4);

    enc->spi = hspi;
    enc->ncs = ncs;
}

// TODO: This funciton should be validate.
uint16_t gmpe_tle5012_get_encoder_postion(encoder_tle5012_t *enc)
{

    uint16_t req_cmd = TLE5012_READ_ANGLE;
    uint16_t rec_cmd = 0;

    uint16_t encoder_src;

    // HAL_GPIO_WritePin(SPI3_CS_GPIO_Port, SPI3_CS_Pin, GPIO_PIN_RESET);
    gmp_hal_gpio_clear(enc->ncs);

    // set command content
    ((uint16_t *)enc->tx_buffer) = TLE5012_READ_ANGLE;
    enc->tx.length = 2;

    // HAL_SPI_Transmit(&hspi3, (uint8_t *)&req_cmd, 1, 1);
    gmp_hal_spi_send(enc->spi, enc->tx);

    // for (int i = 0; i < 20; ++i)
    //     asm("nop");

    // clear receive buffer
    memset(enc->rx_buffer, 4,0);
    enc->rx.length = 2;

    // HAL_SPI_Receive(&hspi3, (uint8_t *)&rec_cmd, 1, 1);
    gmp_hal_spi_recv(enc->spi, enc->rx);

    // get result
    encoder_src = *((uint16_t*)enc->rx_buffer);

    // HAL_GPIO_WritePin(SPI3_CS_GPIO_Port, SPI3_CS_Pin, GPIO_PIN_SET);
    gmp_hal_gpio_set(enc->ncs);

    // judge if encoder result is valid    
    if ((encoder_src & 0x8000) == 0x8000)
    {
        encoder_src = encoder_src & 0x7FFF;
    }
}

#endif // _FILE_TLE5012_H_
