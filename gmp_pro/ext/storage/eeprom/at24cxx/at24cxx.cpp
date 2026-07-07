
// GMP library support
#include <core/gmp_core.hpp>

// extension header
#include <ext/eeprom/at24cxx/at24cxx.h>

size_gt at24cxx::read(addr_type addr, at24cxx::data_type* data, size_gt length)
{
    uint8_t addr_length = iic->get_reg_addr_length();
    iic->set_reg_addr_length(2);
    // Specify the variables address is a Little-endian variable.
    uint16_t lower_address = LE16(addr & 0xFFFF);
    size_gt result = iic->read(dev_addr | ((addr >> 8) & higher_mask), lower_address, (data_gt*)data, length);
    iic->set_reg_addr_length(addr_length); // recover context
    return result;
}

size_gt at24cxx::write(at24cxx::addr_type addr,  at24cxx::data_type* data, size_gt length)
{
    uint8_t addr_length = iic->get_reg_addr_length();
    iic->set_reg_addr_length(2);
    // Specify the variables address is a Little-endian variable.
    uint16_t lower_address = LE16(addr & 0xFFFF);
    size_gt result = iic->write(dev_addr | ((addr >> 8) & higher_mask), lower_address, (data_gt*)data, length);
    iic->set_reg_addr_length(addr_length); // recover context
    return result;
}

at24cxx::cell_type at24cxx::read(at24cxx::addr_type addr)
{
    cell_type result = 0;
    uint8_t addr_length = iic->get_reg_addr_length();
    iic->set_reg_addr_length(2);
    // Specify the variables address is a Little-endian variable.
    uint16_t lower_address = LE16(addr & 0xFFFF); 
    iic->read(dev_addr | ((addr >> 8) & higher_mask), lower_address, (data_gt*)&result, reg_size);
    iic->set_reg_addr_length(addr_length); // recover context
    return result;
}

size_gt at24cxx::write(at24cxx::addr_type addr,  at24cxx::cell_type data)
{
    uint8_t addr_length = iic->get_reg_addr_length();
    iic->set_reg_addr_length(2);
    // Specify the variables address is a Little-endian variable.
    uint16_t lower_address = LE16(addr & 0xFFFF);
    size_gt result = iic->write(dev_addr | ((addr >> 8) & higher_mask), lower_address, ( data_gt*)&data, reg_size);
    iic->set_reg_addr_length(addr_length); // recover context
    return result;
}
