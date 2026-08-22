How the images are built:

Each image is built automatically in the
[anyvm-org/ghostbsd-builder](https://github.com/anyvm-org/ghostbsd-builder)
repo's GitHub Actions: it downloads the official GhostBSD desktop ISO
(MATE / XFCE / Gershwin), boots the live desktop in QEMU, drives its
installer (pc-sysinstall) automatically, enables ssh, pre-installs the
packages listed in the conf, and exports the installed disk as a
compressed qcow2 image.

Upstream install media: the official GhostBSD ISOs from
https://download.ghostbsd.org/releases/ (download page:
https://www.ghostbsd.org/download).
