# Unattended install driver for GhostBSD.
#
# GhostBSD only ships a live GUI installer (gbi), which is a front-end for the
# scriptable pc-sysinstall backend. There is no downloadable VM disk image, so we
# boot the live ISO, reach a root shell on the fully-booted live system, and run
# pc-sysinstall directly with our own answer file (conf/pcinstall.cfg) -- exactly
# the command gbi itself runs: `sudo /usr/local/sbin/pc-sysinstall -c <cfg>`.
#
# This hook is sourced by build.sh (the ISO branch) with $vmsh, $osname,
# waitForText() and string()/enter() already defined, the VNC/OCR screen loop
# running, and a python http.server serving this repo on port 8000 of the build
# host.
#
# IMPORTANT: the screen-driving timings and the live-console login below are the
# parts that need empirical tuning in CI (like every other builder here). They
# are written to be easy to adjust -- see README.md "Status".

set -x

# vbox.sh installs vncdotool on PATH; string()/enter() already use it.
_vnc() { vncdotool "$@"; }

############################################################################
# 0) Work out the IP address the guest uses to reach THIS build host's python
#    http.server (started by build.sh, bound to 0.0.0.0:8000).
#
#    vbox.sh (v1.2.x) always attaches the guest to libvirt's "default" NAT
#    network (virt-install --network network=default), so the host is reachable
#    from the guest at that network's bridge/gateway IP. That is *usually*
#    192.168.122.1, but it depends entirely on the host's libvirt config -- seen
#    in the wild as 192.168.123.1. Hardcoding .122.1 makes the guest's "fetch"
#    fail with "No route to host" on such hosts, so detect the real IP here and
#    only fall back to the common default.
############################################################################
_host_ip=""
# Primary: the <ip address='...'> of the libvirt "default" network.
_host_ip=$( { virsh net-dumpxml default 2>/dev/null || sudo -n virsh net-dumpxml default 2>/dev/null; } \
  | grep -oE "address='[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'" \
  | grep -oE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | head -1 )
# Secondary: the IPv4 on the "default" network's bridge device.
if [ -z "$_host_ip" ]; then
  _br=$( { virsh net-info default 2>/dev/null || sudo -n virsh net-info default 2>/dev/null; } \
    | awk '/^Bridge:/ { print $2 }' )
  [ -n "$_br" ] && _host_ip=$(ip -4 -o addr show "$_br" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
fi
# Tertiary: libvirt's conventional default bridge.
[ -z "$_host_ip" ] && _host_ip=$(ip -4 -o addr show virbr0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
# Final fallback: the historical hardcoded value.
[ -z "$_host_ip" ] && _host_ip="192.168.122.1"
echo "installOpts: guest will fetch the answer file from http://$_host_ip:8000/"
_cfg_url="http://$_host_ip:8000/conf/pcinstall.cfg"

# Trailing shell-comment pad. vncdotool occasionally drops the last few chars it
# types under load; appending a comment pad guarantees a tail-drop eats the pad
# rather than the real command or filename.
_pad="          #zzzzzzzzzzzzzzzz"

############################################################################
# 1) Reach a text-console login prompt.
#
#    The GhostBSD live ISO copies itself into a swap-backed memdisk and REROOTS
#    before the login getty appears. On a slow/contended host that copy can take
#    the better part of an hour, so a single early Ctrl+Alt+F2 is lost across the
#    reroot. Instead we hand waitForText a hook that re-issues Ctrl+Alt+F2 on
#    every poll, so the switch to the text console (ttyv1) is re-asserted until
#    the getty prompt actually appears -- regardless of how long the boot takes.
#    OCR renders the live media's "login:" consistently as "logi".
#
#    We call vbox.sh's waitForText directly (not the build.sh waitForText
#    wrapper) because the wrapper does not forward the 4th "hook" argument.
############################################################################
echo "Waiting for the GhostBSD live system to boot and reach a login prompt..."
sleep 60
_vnc key ctrl-alt-f2
$vmsh waitForText "$osname" "logi" 400 "vncdotool key ctrl-alt-f2"

############################################################################
# 2) Log in. On the GhostBSD live media root logs in on the console with no
#    password. If that ever changes, this is the spot to add a password.
############################################################################
$vmsh string "root"
$vmsh enter
sleep 5
# Harmless extra Enter in case an (empty) password prompt is shown.
$vmsh enter
sleep 15

############################################################################
# 3) Fetch our answer file from the build host and run pc-sysinstall, then power
#    the VM off so build.sh proceeds. We go through sudo so the same line works
#    whether the live login is root or the live user (gbi relies on passwordless
#    sudo on the live media). The fetch is issued twice (it is idempotent) to
#    ride out a transient hiccup just after the live network comes up.
############################################################################
$vmsh string "sudo fetch -o /tmp/pcinstall.cfg $_cfg_url$_pad"
$vmsh enter
sleep 12
$vmsh string "sudo fetch -o /tmp/pcinstall.cfg $_cfg_url$_pad"
$vmsh enter
sleep 8
# Show the config in the build log for debugging.
$vmsh string "cat /tmp/pcinstall.cfg$_pad"
$vmsh enter
sleep 3

$vmsh string "sudo /usr/local/sbin/pc-sysinstall -c /tmp/pcinstall.cfg$_pad"
$vmsh enter

# Give pc-sysinstall time to partition, create the pool and clone the live
# filesystem to disk. build.sh waits for the VM to power off after this hook
# returns, so block here until the install is plausibly done.
echo "Running pc-sysinstall; waiting for it to finish..."
# pc-sysinstall prints "Installation finished!" on success (OCR sees the "!"
# as "?"), so match the OCR-robust substring "finished".
waitForText "finished" 1200 || true

sleep 10
$vmsh string "sudo shutdown -p now$_pad"
$vmsh enter
