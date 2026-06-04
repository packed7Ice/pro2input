import sys
import subprocess
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Direct Path Test for Switch 2 Pro Controller
#  Uses PowerShell to find the exact device path after Zadig replacement.
# ---------------------------------------------------------------------------

TARGET_VID = "VID_057E"
TARGET_PID = "PID_2069"

kernel32 = ctypes.windll.kernel32


def get_device_path_via_powershell():
    """Use PowerShell to find the device instance path for the controller."""
    ps_command = """
    $dev = Get-PnpDevice | Where-Object { $_.InstanceId -like '*VID_057E*PID_2069*' } | Select-Object -First 1
    if ($dev) { $dev.InstanceId } else { 'NOT_FOUND' }
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        if output and output != "NOT_FOUND":
            # Convert instance ID to device path format
            # HID\VID_057E&PID_2069&MI_00\9&2FF21532&0&0000
            # -> \\?\hid#vid_057e&pid_2069&mi_00#9&2ff21532&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}
            
            # We need the actual device interface path, not just instance ID
            # Let's query WMI for the device path
            return output
    except Exception as e:
        print(f"[WARN] PowerShell query failed: {e}")
    return None


def get_interface_path_via_powershell():
    """Get the actual device interface path using WMI."""
    ps_command = r"""
    $devices = Get-WmiObject Win32_PNPEntity | Where-Object { $_.DeviceID -like '*VID_057E*PID_2069*' }
    foreach ($dev in $devices) {
        Write-Output "INSTANCE:$($dev.DeviceID)"
        # Try to get the device path from the registry or by finding child interfaces
    }
    
    # Alternative: look for the device path in the Device Manager properties
    $paths = Get-PnpDeviceProperty -InstanceId (Get-PnpDevice | Where-Object { $_.InstanceId -like '*VID_057E*PID_2069*' } | Select-Object -First 1).InstanceId -KeyName 'DEVPKEY_Device_Driver' -ErrorAction SilentlyContinue
    Write-Output "PATHS_FOUND"
    """
    
    # Simpler approach: list all device interface paths that contain 057E/2069 using WMI
    ps_command2 = r"""
    $pattern = '*057e*2069*'
    $query = "SELECT * FROM Win32_PnPEntity WHERE DeviceID LIKE '$pattern'"
    $devices = Get-WmiObject -Query $query
    foreach ($dev in $devices) {
        Write-Output "DEV:$($dev.DeviceID)|NAME:$($dev.Name)|STATUS:$($dev.Status)"
    }
    """
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command2],
            capture_output=True, text=True, timeout=10
        )
        print(f"[PS-OUT] {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"[PS-ERR] {result.stderr.strip()}")
        return result.stdout.strip()
    except Exception as e:
        print(f"[WARN] PowerShell query failed: {e}")
        return None


def open_device(path):
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle == ctypes.c_void_p(-1).value:
        return None
    return handle


def write_device(handle, data, report_size=64):
    if len(data) < report_size:
        data = data + [0] * (report_size - len(data))
    elif len(data) > report_size:
        data = data[:report_size]
    buf = (ctypes.c_ubyte * len(data))(*data)
    written = wintypes.DWORD(0)
    ret = kernel32.WriteFile(handle, buf, len(data), ctypes.byref(written), None)
    if not ret:
        print(f"  [WARN] WriteFile failed. Error: {kernel32.GetLastError()}")
        return False
    return True


def read_device(handle, size, timeout_ms=5000):
    buf = (ctypes.c_ubyte * size)()
    read_count = wintypes.DWORD(0)
    ret = kernel32.ReadFile(handle, buf, size, ctypes.byref(read_count), None)
    if ret:
        return bytes(buf[:read_count.value])
    return None


def try_known_paths():
    """Try the known path from before Zadig, and any variations."""
    # The path we saw before in list_all_hid.py
    known_paths = [
        r"\\?\hid#vid_057e&pid_2069&mi_00#9&2ff21532&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}",
    ]
    
    # Also try to get the path from registry via PowerShell
    ps_cmd = r"""
    $regPath = 'HKLM:\SYSTEM\CurrentControlSet\Enum\HID\VID_057E&PID_2069&MI_00'
    if (Test-Path $regPath) {
        Get-ChildItem $regPath | ForEach-Object {
            $instance = $_.PSChildName
            Write-Output "INSTANCE:$instance"
        }
    } else {
        Write-Output 'NO_REG'
    }
    """
    
    try:
        result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        print(f"[REG-OUT] {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"[REG-ERR] {result.stderr.strip()}")
    except Exception as e:
        print(f"[WARN] Registry query failed: {e}")
    
    return known_paths


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Direct Path Test")
    print("=" * 80)

    # First, let's see what PowerShell says about the device
    print("\n[INFO] Querying device status via PowerShell...")
    get_interface_path_via_powershell()
    
    # Try known paths
    print("\n[INFO] Trying known device paths...")
    paths = try_known_paths()
    
    for path in paths:
        print(f"\n[TRY] Opening: {path}")
        handle = open_device(path)
        if not handle:
            err = kernel32.GetLastError()
            print(f"[NG ] CreateFile failed. Error: {err}")
            continue
        
        print(f"[OK ] Handle opened: {handle}")
        
        # Try simple write
        print("  [INIT] Trying: 64-byte zeros")
        if write_device(handle, [0x00] * 64):
            time.sleep(0.3)
            peek = read_device(handle, 64, timeout_ms=500)
            if peek:
                print(f"  [OK ] Controller responded ({len(peek)} bytes).")
                
                print("\n" + "=" * 80)
                print("[READ] Entering main read loop. Press Ctrl+C to stop.")
                print("=" * 80)
                
                last = None
                try:
                    while True:
                        data = read_device(handle, 64, timeout_ms=5000)
                        if data:
                            hex_str = " ".join(f"{b:02X}" for b in data)
                            if data != last:
                                marker = "  <-- CHANGE"
                                last = list(data)
                            else:
                                marker = ""
                            print(f"RECV [{len(data):2d}]: {hex_str}{marker}")
                        else:
                            print(".", end="", flush=True)
                except KeyboardInterrupt:
                    print("\n[INFO] Interrupted by user.")
                
                kernel32.CloseHandle(handle)
                return
            else:
                print("  [INFO] No immediate response, trying more init sequences...")
        else:
            print("  [WARN] Write failed.")
        
        kernel32.CloseHandle(handle)

    print("\n[FATAL] Could not initialize via known paths.")
    print("\nLet's try to find the new device path after Zadig...")
    
    # Query for any device path containing 057e/2069
    ps_cmd2 = r"""
    # Search for device interface paths in the registry
    $key = Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses' -Recurse -ErrorAction SilentlyContinue | 
        Where-Object { $_.Name -like '*057e*2069*' }
    if ($key) { Write-Output "FOUND:$($key.Name)" } else { Write-Output 'NOT_FOUND' }
    """
    
    try:
        result = subprocess.run(["powershell", "-Command", ps_cmd2], capture_output=True, text=True, timeout=15)
        print(f"[SEARCH] {result.stdout.strip()}")
    except Exception as e:
        print(f"[WARN] Search failed: {e}")
    
    print("\n[INFO] Please check Device Manager for the current device path.")
    print("       Device Manager -> View -> Devices by connection")
    print("       Look for Nintendo Switch Pro Controller -> Properties -> Details -> Device instance path")


if __name__ == "__main__":
    main()
