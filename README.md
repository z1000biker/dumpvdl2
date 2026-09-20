# dumpvdl2 Windows x64

Unofficial Windows x64 port/build of [dumpvdl2](https://github.com/szpajder/dumpvdl2), based on upstream **v2.7.0**.

This repository contains the Windows compatibility patch and a reproducible GitHub Actions build. The workflow builds a portable x64 package with:

- RTL-SDR support
- libacars 2.2.1
- SQLite
- ZeroMQ
- protobuf-c raw binary output

The Windows build uses MSYS2 UCRT64 / MinGW-w64.

## Status

The generated `dumpvdl2.exe` has been smoke-tested on Windows and the RTL-SDR input path has been tested with an **RTL-SDR Blog V4**: the device, R828D tuner, sample rate and 136.975 MHz tuning were detected correctly and streaming started successfully.

A full end-to-end VDL2 decode test depends on live traffic and RF conditions.

## Run

Extract the release ZIP and keep all DLLs beside `dumpvdl2.exe`.

Basic VDL2 reception on 136.975 MHz:

```powershell
.\dumpvdl2.exe --rtlsdr 0 136.975M
```

With manual gain:

```powershell
.\dumpvdl2.exe --rtlsdr 0 --gain 38 136.975M
```

Only enable Bias-T if your antenna/LNA actually requires power:

```powershell
.\dumpvdl2.exe --rtlsdr 0 --gain 38 --bias 1 136.975M
```

## Windows compatibility changes

The patch keeps the normal POSIX path unchanged and adds Windows-specific handling for:

- `sigaction` / POSIX-only signals
- `strsep` and `strndup`
- `time_t` compatibility
- `arpa/inet.h` replacements
- Winsock2 UDP handling
- `gmtime_r` / `localtime_r`
- linking against `ws2_32`

## Raspberry Pi builds

Prebuilt Raspberry Pi packages are also generated from upstream **dumpvdl2 v2.7.0** with **libacars 2.2.1**.

Two builds are provided:

- `dumpvdl2-2.7.0-raspberrypi-arm64.tar.gz` — for Raspberry Pi OS **64-bit** (`aarch64`)
- `dumpvdl2-2.7.0-raspberrypi-armhf.tar.gz` — for Raspberry Pi OS **32-bit** (`ARMv7/armhf`)

They are built in Debian Bookworm environments and include support for:

- RTL-SDR
- SQLite
- ZeroMQ
- protobuf-c raw binary output

The packages include the `dumpvdl2` executable, bundled `libacars`, a small launcher script and build information.

Install the runtime dependencies on Raspberry Pi OS:

```bash
sudo apt update
sudo apt install -y librtlsdr0 libglib2.0-0 libsqlite3-0 libprotobuf-c1 libzmq5
```

Extract the appropriate package and run:

```bash
./run-dumpvdl2.sh --rtlsdr 0 --gain 38 136.975M
```

The ARM64 and ARMv7/armhf GitHub Actions builds both complete successfully. They have not yet been hardware-tested on a physical Raspberry Pi, so the build status confirms successful ARM compilation and packaging, not yet an end-to-end RF decode test on Raspberry Pi hardware.

## Upstream

Original project: https://github.com/szpajder/dumpvdl2

Original author: szpajder

This is an unofficial Windows port/build and is not an official upstream Windows release.

## License

dumpvdl2 is licensed under GPL-3.0-or-later. See the upstream project for the original source and licensing information.
