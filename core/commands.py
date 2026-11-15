"""The shell commands sent to the phone, and the system properties we keep."""


FAST_CMD = (
    "grep ^cpu /proc/stat; "
    "echo @@MEM; cat /proc/meminfo; "
    "echo @@BAT; dumpsys battery; "
    "echo @@PS; for f in capacity current_now voltage_now charge_full charge_full_design charge_counter "
    "cycle_count status health technology; do echo \"$f=$(cat /sys/class/power_supply/battery/$f 2>/dev/null)\"; done; "
    "echo @@DF; df -k /data; "
    "echo @@NET; cat /proc/net/dev; "
    "echo @@FREQ; for c in /sys/devices/system/cpu/cpu[0-9]*; do "
    "echo \"$(basename $c) $(cat $c/cpufreq/scaling_cur_freq 2>/dev/null) $(cat $c/cpufreq/cpuinfo_max_freq 2>/dev/null)\"; done; "
    "echo @@THERM; for z in /sys/class/thermal/thermal_zone*; do echo \"$(cat $z/type 2>/dev/null)|$(cat $z/temp 2>/dev/null)\"; done; "
    "echo @@UP; cat /proc/uptime; cat /proc/loadavg"
)


DIAG_CMD = (
    "echo @@PROPS; getprop; "
    "echo @@SEL; getenforce 2>/dev/null; "
    "echo @@SU; which su 2>/dev/null; ls /system/xbin/su /system/bin/su /sbin/su /su/bin/su 2>/dev/null; "
    "echo @@PKG; pm list packages -3 2>/dev/null | wc -l; pm list packages -s 2>/dev/null | wc -l; "
    "pm list packages -d 2>/dev/null | wc -l; "
    "echo @@WM; wm size 2>/dev/null; wm density 2>/dev/null; "
    "echo @@PWR; dumpsys power 2>/dev/null | grep -m4 -E 'mWakefulness=|mIsPowered=|Display Power'; "
    "echo @@WIFI; dumpsys wifi 2>/dev/null | grep -m1 'mWifiInfo'; "
    "echo @@CRASH; logcat -b crash -d -t 300 2>/dev/null | grep -c 'FATAL EXCEPTION'; "
    "echo @@ANR; logcat -b events -d -t 1000 2>/dev/null | grep -c am_anr; "
    "echo @@END"
)


PROP_KEYS = [
    "ro.product.manufacturer", "ro.product.brand", "ro.product.model", "ro.product.device", "ro.product.name",
    "ro.build.version.release", "ro.build.version.sdk", "ro.build.version.security_patch", "ro.build.type",
    "ro.build.tags", "ro.build.fingerprint", "ro.product.cpu.abi", "ro.hardware", "ro.board.platform",
    "ro.boot.verifiedbootstate", "ro.boot.flash.locked", "ro.crypto.state", "ro.debuggable",
    "gsm.operator.alpha", "persist.sys.timezone",
]
