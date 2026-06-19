

[![Build](https://github.com/anyvm-org/ghostbsd-builder/actions/workflows/build.yml/badge.svg)](https://github.com/anyvm-org/ghostbsd-builder/actions/workflows/build.yml)

Latest: v2.0.5


The image builder for `ghostbsd`


All the supported releases are here:



| Release         | x86_64 |
|-----------------|--------|
| 26.1            |  ✅ (rsync,scp,sshfs,nfs)    |

GhostBSD is published as amd64 (x86_64) only. The release above is the official
MATE image (`26.1`).



GhostBSD desktop variant images (x86_64):

| Release         | x86_64 |
|-----------------|--------|
| 26.1-xfce       |  ✅    |
| 26.1-gershwin   |  ✅    |

These are the community XFCE image (`26.1-xfce`) and the community GNUstep
"Gershwin" preview (`26.1-gershwin`). The default `26.1` image (MATE) is listed
in the main table.


How to build:

1. Use the [manual.yml](.github/workflows/manual.yml) to build manually.
   
    Run the workflow manually, you will get a view-only webconsole from the output of the workflow, just open the link in your web browser.
   
    You will also get an interactive VNC connection port from the output, you can connect to the vm by any vnc client.

2. Run the builder locally on your Ubuntu machine.

    Just clone the repo. and run:
    ```bash
    python3 build.py conf/ghostbsd-26.1.conf
    ```
   
