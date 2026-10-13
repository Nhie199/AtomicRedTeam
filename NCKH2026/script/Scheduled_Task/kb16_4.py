import time
import sys
import winrm

# ==============================================================
# KỊCH BẢN 16 - SCHEDULED TASK
#
# Mục tiêu:
#   A. Native Windows behavior -> log thật
#      - Security 4698 : Task Created
#      - Security 4702 : Task Updated
#      - Security 4699 : Task Deleted
#      - TaskScheduler/Operational
#      - Sysmon Event ID 1
#      - File creation / marker
#
#   B. Atomic Red Team
#      - T1053.005 Scheduled Task
#      - T1021.002 SMB/Windows Admin Shares
#
# Payload native chỉ ghi marker vào C:\Windows\Temp
# Không tải payload, không C2, không shell ngược.
# ==============================================================

WIN_HOST = "192.168.200.20"
WIN_USER = "ansible"
WIN_PASS = "19092005"

# Không có máy thứ 2 -> để []
# Ví dụ khi có máy thứ 2:
# LATERAL_HOSTS = ["192.168.200.21"]
LATERAL_HOSTS = []

TASK_NAME = "OneDriveSyncHelper"

MARKER_DIR = r"C:\Windows\Temp\atomic_kb16"
MARKER_FILE = r"C:\Windows\Temp\atomic_kb16\marker.log"

# Payload vô hại.
TASK_ACTION = (
    r'cmd.exe /c echo Atomic-KB16-Marker-%DATE%-%TIME% '
    r'>> C:\Windows\Temp\atomic_kb16\marker.log'
)

# --------------------------------------------------------------
# WinRM
# --------------------------------------------------------------

session = winrm.Session(
    f"http://{WIN_HOST}:5985/wsman",
    auth=(WIN_USER, WIN_PASS),
    transport="ntlm"
)


def run_cmd(cmd, label):
    print(f"\n[*] {label}")
    print(f"    CMD: {cmd}")

    try:
        result = session.run_cmd(cmd)

        stdout = result.std_out.decode(
            "utf-8", errors="ignore"
        ).strip()

        stderr = result.std_err.decode(
            "utf-8", errors="ignore"
        ).strip()

        if result.status_code == 0:
            print("    [+] SUCCESS")

            if stdout:
                print("    [OUT]")
                print(stdout[:2000])

        else:
            print(f"    [-] FAILED: {result.status_code}")

            if stdout:
                print("    [OUT]")
                print(stdout[:1000])

            if stderr:
                print("    [ERR]")
                print(stderr[:1000])

        return result.status_code, stdout

    except Exception as e:
        print(f"    [!] Exception: {e}")
        return -1, ""


def run_ps(ps, label):
    """
    Chạy PowerShell qua WinRM.
    """
    encoded = ps.encode("utf-16le")
    import base64

    encoded_cmd = base64.b64encode(encoded).decode()

    return run_cmd(
        f"powershell.exe -NoProfile -EncodedCommand {encoded_cmd}",
        label
    )


# ==============================================================
# PRECHECK
# ==============================================================

def precheck():

    print("\n" + "=" * 72)
    print("[*] PRECHECK")
    print("=" * 72)

    run_cmd(
        "whoami",
        "Check Windows user"
    )

    run_cmd(
        "hostname",
        "Check hostname"
    )

    run_cmd(
        "schtasks /query /tn "
        f'"{TASK_NAME}"',
        "Check existing task"
    )

    run_ps(
        "Get-ExecutionPolicy -List",
        "Check PowerShell execution policy"
    )


# ==============================================================
# CREATE MARKER DIRECTORY
# ==============================================================

def prepare_marker():

    ps = (
        f'New-Item -ItemType Directory '
        f'-Path "{MARKER_DIR}" '
        f'-Force | Out-Null; '
        f'Write-Host "Marker directory ready"'
    )

    run_ps(
        ps,
        "Prepare harmless marker directory"
    )


# ==============================================================
# STEP 1
# T1053.005 - CREATE
# ==============================================================
#
# Expected:
#
# Security:
#   4698
#
# TaskScheduler:
#   registration events
#
# Sysmon:
#   Event ID 1 -> schtasks.exe
#
# ==============================================================

def create_task():

    cmd = (
        f'schtasks.exe /create '
        f'/tn "{TASK_NAME}" '
        f'/tr "{TASK_ACTION}" '
        f'/sc onlogon '
        f'/ru SYSTEM '
        f'/rl LIMITED '
        f'/f'
    )

    return run_cmd(
        cmd,
        "[1] T1053.005 - Create Scheduled Task"
    )


# ==============================================================
# STEP 2
# T1053.005 - QUERY
# ==============================================================
#
# Mục đích:
#   chứng minh task tồn tại và thu thập configuration.
#
# ==============================================================

def query_task():

    cmd = (
        f'schtasks.exe /query '
        f'/tn "{TASK_NAME}" '
        f'/v /fo LIST'
    )

    return run_cmd(
        cmd,
        "[2] T1053.005 - Query Scheduled Task"
    )


# ==============================================================
# STEP 3
# T1053.005 - EXECUTE
# ==============================================================
#
# Task chạy thật.
#
# Expected:
#   TaskScheduler Operational
#   Sysmon Event ID 1
#   marker file creation
#
# ==============================================================

def run_task():

    cmd = (
        f'schtasks.exe /run '
        f'/tn "{TASK_NAME}"'
    )

    return run_cmd(
        cmd,
        "[3] T1053.005 - Run Scheduled Task"
    )


# ==============================================================
# STEP 4
# T1053.005 - MODIFY
# ==============================================================
#
# Đây là bước QUAN TRỌNG để sinh 4702.
#
# Thay đổi trigger từ ONLOGON thành MINUTE.
#
# ==============================================================

def modify_task():

    cmd = (
        f'schtasks.exe /change '
        f'/tn "{TASK_NAME}" '
        f'/sc minute '
        f'/mo 5'
    )

    return run_cmd(
        cmd,
        "[4] T1053.005 - Modify Scheduled Task -> 4702"
    )


# ==============================================================
# STEP 5
# RUN AFTER MODIFY
# ==============================================================

def run_modified_task():

    cmd = (
        f'schtasks.exe /run '
        f'/tn "{TASK_NAME}"'
    )

    return run_cmd(
        cmd,
        "[5] Execute Modified Scheduled Task"
    )


# ==============================================================
# STEP 6
# VERIFY MARKER
# ==============================================================

def verify_marker():

    ps = (
        f'Write-Host "===== MARKER ====="; '
        f'if (Test-Path "{MARKER_FILE}") {{ '
        f'Get-Content "{MARKER_FILE}" '
        f'}} else {{ '
        f'Write-Host "Marker not found" '
        f'}}'
    )

    return run_ps(
        ps,
        "[6] Verify Task Execution Marker"
    )


# ==============================================================
# STEP 7
# ATOMIC RED TEAM
#
# Không tự giả lập Atomic.
# Kiểm tra module trước.
# ==============================================================

def atomic_check():

    ps = r'''
$ErrorActionPreference="SilentlyContinue"

if (Get-Command Invoke-AtomicTest) {
    Write-Host "Invoke-AtomicTest AVAILABLE"
    Get-Command Invoke-AtomicTest
} else {
    Write-Host "Invoke-AtomicTest NOT FOUND"
}
'''

    return run_ps(
        ps,
        "[7] Check Invoke-AtomicRedTeam"
    )


# ==============================================================
# STEP 8
# ATOMIC T1053.005
#
# ShowDetails trước.
# Sau đó chạy test nếu tồn tại.
# ==============================================================

def atomic_t1053():

    ps = r'''
$ErrorActionPreference="Continue"

Write-Host "===== ATOMIC T1053.005 ====="

Invoke-AtomicTest T1053.005 -ShowDetailsBrief

Write-Host "===== RUN ATOMIC T1053.005 ====="

Invoke-AtomicTest T1053.005
'''

    return run_ps(
        ps,
        "[8] Atomic Red Team - T1053.005"
    )


# ==============================================================
# STEP 9
# ATOMIC T1021.002
#
# Chỉ thực hiện nếu atomics có test.
#
# Lưu ý:
# Không có host thứ 2 thì đây KHÔNG phải lateral movement
# thực sự.
# ==============================================================

def atomic_t1021():

    ps = r'''
$ErrorActionPreference="Continue"

Write-Host "===== ATOMIC T1021.002 ====="

Invoke-AtomicTest T1021.002 -ShowDetailsBrief

Write-Host "===== RUN ATOMIC T1021.002 ====="

Invoke-AtomicTest T1021.002
'''

    return run_ps(
        ps,
        "[9] Atomic Red Team - T1021.002"
    )


# ==============================================================
# STEP 10
# OPTIONAL REAL LATERAL MOVEMENT
#
# Chỉ chạy khi có host thứ 2.
# ==============================================================

def lateral_movement():

    if not LATERAL_HOSTS:

        print(
            "\n[!] T1021.002 NATIVE LATERAL MOVEMENT: SKIPPED"
        )

        print(
            "[!] Không có host thứ 2 trong lab."
        )

        return

    for host in LATERAL_HOSTS:

        remote_task = (
            f'schtasks.exe /create '
            f'/s {host} '
            f'/u {WIN_USER} '
            f'/p {WIN_PASS} '
            f'/tn "{TASK_NAME}" '
            f'/tr "{TASK_ACTION}" '
            f'/sc onlogon '
            f'/f'
        )

        run_cmd(
            remote_task,
            f"[10] T1021.002 - Remote Task Creation -> {host}"
        )


# ==============================================================
# STEP 11
# DELETE
#
# Expected:
#
# Security:
#   4699
#
# TaskScheduler:
#   delete/unregister
#
# ==============================================================

def delete_task():

    cmd = (
        f'schtasks.exe /delete '
        f'/tn "{TASK_NAME}" '
        f'/f'
    )

    return run_cmd(
        cmd,
        "[11] T1053.005 - Delete Scheduled Task -> 4699"
    )


# ==============================================================
# FINAL COLLECTION
# ==============================================================

def final_collection():

    print("\n" + "=" * 72)
    print("[*] FINAL VERIFICATION")
    print("=" * 72)

    run_cmd(
        f'schtasks.exe /query /tn "{TASK_NAME}"',
        "Verify task removed"
    )

    run_ps(
        f'Get-ChildItem "{MARKER_DIR}" -Force',
        "Verify marker artifact"
    )


# ==============================================================
# MAIN
# ==============================================================

def main():

    print("=" * 72)
    print(
        f"[*] KỊCH BẢN 16 - SCHEDULED TASK "
        f"(NATIVE + ATOMIC RED TEAM)"
    )
    print(f"[*] Target: {WIN_HOST}")
    print("=" * 72)

    precheck()

    time.sleep(2)

    prepare_marker()

    time.sleep(2)

    create_task()

    time.sleep(2)

    query_task()

    time.sleep(2)

    run_task()

    time.sleep(4)

    modify_task()

    time.sleep(2)

    run_modified_task()

    time.sleep(4)

    verify_marker()

    time.sleep(2)

    atomic_check()

    time.sleep(2)

    atomic_t1053()

    time.sleep(2)

    atomic_t1021()

    time.sleep(2)

    lateral_movement()

    time.sleep(2)

    delete_task()

    time.sleep(2)

    final_collection()

    print("\n" + "=" * 72)
    print("[✓] SCENARIO FINISHED")
    print("=" * 72)

    print("""
Expected telemetry:

[Windows Security]
  4698 -> Scheduled Task Created
  4702 -> Scheduled Task Modified
  4699 -> Scheduled Task Deleted
  4624 Type 3 -> only with remote SMB access
  5140 -> only when an SMB share is actually accessed

[TaskScheduler/Operational]
  Task registration
  Task update
  Task launch
  Task completion
  Task deletion

[Sysmon]
  Event ID 1 -> schtasks.exe
  Event ID 1 -> powershell.exe
  Event ID 1 -> task-related process
  Event ID 11 -> marker file creation (if FileCreate enabled)
  Event ID 3 -> network connection when applicable

[Atomic Red Team]
  T1053.005
  T1021.002

[Artifact]
  C:\\Windows\\Temp\\atomic_kb16\\marker.log
""")


if __name__ == "__main__":
    main()
