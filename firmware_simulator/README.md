# Firmware Simulator (Optional C Module)

This directory contains an optional C implementation of the virtual chip simulator,
demonstrating the same register map and SRAM test concepts in a compiled language.

## Purpose

- Demonstrates portability of the validation concepts beyond Python
- Shows register-level access control in C
- Implements walking ones and checkerboard SRAM tests in C
- Useful for interview portfolio or embedded firmware discussion

## Build

```bash
gcc -Wall -Wextra -o firmware_sim main.c
```

## Run

```bash
./firmware_sim
```

## Expected Output

```
=== Virtual Silicon Firmware Simulator ===

[CHIP] Powered ON. Device ID=0xA5 FW=1.0

[REG] Device ID:       0xA5
[REG] Firmware:        1.0

[REG] Writing POWER_CONTROL=0x01...
[REG] POWER_CONTROL = 0x01

[REG] Attempting write to read-only DEVICE_ID...
[ERR] Register 0x00 is read-only.

[MEM] SRAM Tests:
[MEM] Running walking ones test... PASS
[MEM] Running checkerboard test... PASS

[CHIP] Cycles executed: 6

=== Simulation complete. Status: PASS ===
```

## Notes

- This module is **not required** by the Python test suite
- It is compiled and run independently
- The Python platform (`src/virtual_silicon/`) is the primary implementation
