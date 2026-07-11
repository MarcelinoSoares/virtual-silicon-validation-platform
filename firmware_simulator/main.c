/**
 * firmware_simulator/main.c
 *
 * Optional C firmware simulator for virtual chip register behavior.
 * Demonstrates the same register map and SRAM concepts in C.
 * Not required for the Python test suite — provided for portfolio completeness.
 *
 * Build: gcc -Wall -Wextra -o firmware_sim main.c
 * Run:   ./firmware_sim
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* ── Register addresses ─────────────────────────────────────────────────── */
#define REG_DEVICE_ID       0x00
#define REG_DEVICE_STATUS   0x01
#define REG_POWER_CONTROL   0x02
#define REG_TEMPERATURE     0x03
#define REG_VOLTAGE_HIGH    0x04
#define REG_VOLTAGE_LOW     0x05
#define REG_CURRENT_HIGH    0x06
#define REG_CURRENT_LOW     0x07
#define REG_DISPLAY_CONFIG  0x08
#define REG_ERROR_FLAGS     0x09
#define REG_FW_VER_HIGH     0x0A
#define REG_FW_VER_LOW      0x0B
#define REG_INT_STATUS      0x0C
#define REG_COUNT           0x0D

#define SRAM_SIZE           256
#define DEVICE_ID_VAL       0xA5
#define FW_MAJOR            1
#define FW_MINOR            0

/* ── Chip state ─────────────────────────────────────────────────────────── */
typedef struct {
    uint8_t registers[REG_COUNT];
    uint8_t sram[SRAM_SIZE];
    int     powered;
    uint32_t cycle_count;
} VirtualChip;

/* ── Chip operations ─────────────────────────────────────────────────────── */
static void chip_power_on(VirtualChip *chip) {
    memset(chip->registers, 0x00, sizeof(chip->registers));
    memset(chip->sram, 0x00, sizeof(chip->sram));
    chip->registers[REG_DEVICE_ID]    = DEVICE_ID_VAL;
    chip->registers[REG_TEMPERATURE]  = 0x19;  /* 25°C */
    chip->registers[REG_VOLTAGE_HIGH] = 0x0C;
    chip->registers[REG_VOLTAGE_LOW]  = 0x80;
    chip->registers[REG_CURRENT_HIGH] = 0x00;
    chip->registers[REG_CURRENT_LOW]  = 0x64;
    chip->registers[REG_DISPLAY_CONFIG] = 0x80;
    chip->registers[REG_FW_VER_HIGH]  = FW_MAJOR;
    chip->registers[REG_FW_VER_LOW]   = FW_MINOR;
    chip->powered     = 1;
    chip->cycle_count = 0;
    printf("[CHIP] Powered ON. Device ID=0x%02X FW=%d.%d\n",
           DEVICE_ID_VAL, FW_MAJOR, FW_MINOR);
}

static uint8_t reg_read(VirtualChip *chip, uint8_t addr) {
    if (!chip->powered) { printf("[ERR] Chip not powered.\n"); return 0xFF; }
    if (addr >= REG_COUNT) { printf("[ERR] Invalid register 0x%02X.\n", addr); return 0xFF; }
    chip->cycle_count++;
    return chip->registers[addr];
}

static int reg_write(VirtualChip *chip, uint8_t addr, uint8_t value) {
    if (!chip->powered) { printf("[ERR] Chip not powered.\n"); return -1; }
    /* DEVICE_ID, DEVICE_STATUS, TEMPERATURE, VOLTAGE, CURRENT, FW_VER are read-only */
    if (addr == REG_DEVICE_ID || addr == REG_DEVICE_STATUS ||
        addr == REG_TEMPERATURE || addr == REG_VOLTAGE_HIGH ||
        addr == REG_VOLTAGE_LOW || addr == REG_CURRENT_HIGH ||
        addr == REG_CURRENT_LOW || addr == REG_FW_VER_HIGH ||
        addr == REG_FW_VER_LOW) {
        printf("[ERR] Register 0x%02X is read-only.\n", addr);
        return -1;
    }
    if (addr >= REG_COUNT) { printf("[ERR] Invalid register 0x%02X.\n", addr); return -1; }
    chip->registers[addr] = value;
    chip->cycle_count++;
    return 0;
}

/* Walking ones memory test */
static int sram_test_walking_ones(VirtualChip *chip) {
    printf("[MEM] Running walking ones test... ");
    for (int addr = 0; addr < SRAM_SIZE; addr++) {
        for (int bit = 0; bit < 8; bit++) {
            uint8_t pattern = (uint8_t)(1 << bit);
            chip->sram[addr] = pattern;
            if (chip->sram[addr] != pattern) {
                printf("FAIL at addr=%d bit=%d\n", addr, bit);
                return -1;
            }
        }
    }
    printf("PASS\n");
    return 0;
}

/* Checkerboard memory test */
static int sram_test_checkerboard(VirtualChip *chip) {
    printf("[MEM] Running checkerboard test... ");
    for (int addr = 0; addr < SRAM_SIZE; addr++) {
        chip->sram[addr] = (addr % 2 == 0) ? 0x55 : 0xAA;
    }
    for (int addr = 0; addr < SRAM_SIZE; addr++) {
        uint8_t expected = (addr % 2 == 0) ? 0x55 : 0xAA;
        if (chip->sram[addr] != expected) {
            printf("FAIL at addr=%d\n", addr);
            return -1;
        }
    }
    printf("PASS\n");
    return 0;
}

int main(void) {
    VirtualChip chip;
    memset(&chip, 0, sizeof(chip));

    printf("=== Virtual Silicon Firmware Simulator ===\n\n");

    chip_power_on(&chip);

    printf("\n[REG] Device ID:       0x%02X\n", reg_read(&chip, REG_DEVICE_ID));
    printf("[REG] Firmware:        %d.%d\n",
           reg_read(&chip, REG_FW_VER_HIGH), reg_read(&chip, REG_FW_VER_LOW));

    printf("\n[REG] Writing POWER_CONTROL=0x01...\n");
    reg_write(&chip, REG_POWER_CONTROL, 0x01);
    printf("[REG] POWER_CONTROL = 0x%02X\n", reg_read(&chip, REG_POWER_CONTROL));

    printf("\n[REG] Attempting write to read-only DEVICE_ID...\n");
    reg_write(&chip, REG_DEVICE_ID, 0x00);

    printf("\n[MEM] SRAM Tests:\n");
    int ok = 0;
    ok += sram_test_walking_ones(&chip);
    ok += sram_test_checkerboard(&chip);

    printf("\n[CHIP] Cycles executed: %u\n", chip.cycle_count);
    printf("\n=== Simulation complete. Status: %s ===\n",
           ok == 0 ? "PASS" : "FAIL");

    return ok == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
