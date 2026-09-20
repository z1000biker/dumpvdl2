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

## Upstream

Original project: https://github.com/szpajder/dumpvdl2

Original author: szpajder

This is an unofficial Windows port/build and is not an official upstream Windows release.

## License

dumpvdl2 is licensed under GPL-3.0-or-later. See the upstream project for the original source and licensing information.
