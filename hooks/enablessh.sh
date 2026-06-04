#!/bin/sh
# Sourced by build.sh to authorize the builder's SSH key on the installed VM.
#
# It exists to OVERRIDE build.sh's default VM_USE_SSHROOT_BUILD_SSH path, which
# pipes enablessh.local into:
#     sshpass ... ssh -tt root@<vm> TERM=xterm <enablessh.local
# OpenSSH runs the literal remote command "TERM=xterm" -- a no-op variable
# assignment that never reads stdin -- and the forced pty (-tt) only ECHOES the
# piped script back without executing it. On GhostBSD (root shell /bin/sh) the
# result is that /root/.ssh is never created and the builder's public key is
# never added to authorized_keys, so every later key-based ssh fails with
# "Received disconnect ... Too many authentication failures" (exit 255).
#
# Feeding the same script to an explicit `sh` actually executes it, which is all
# this hook changes. enablessh.local was already assembled by build.sh (this hook
# runs right after), and $vmsh / $osname / $VM_ROOT_PASSWORD are in scope.

vmip=$($vmsh getVMIP "$osname")
echo "enablessh.sh: authorizing builder key on $osname at $vmip (via 'ssh ... sh')"

sshpass -p "$VM_ROOT_PASSWORD" ssh \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o PreferredAuthentications=password -o PubkeyAuthentication=no \
  root@"$vmip" sh <enablessh.local

# Give sshd a moment; build.sh's own retry loop verifies key-based access next.
sleep 5
