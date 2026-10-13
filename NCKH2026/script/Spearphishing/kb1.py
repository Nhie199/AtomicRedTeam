import time
import base64
import winrm

# ==============================================================
# KỊCH BẢN 01 - SPEARPHISHING ATTACHMENT / OFFICE MACRO
#
# Mục tiêu:
#
# A. Native Windows behavior -> tạo telemetry thật
#
# - Tạo file Office giả lập (.docm)
# - Tạo marker
# - WINWORD.EXE mở file
# - PowerShell tạo marker benign
# - Sysmon Event ID 1
# - Sysmon Event ID 11
# - PowerShell 4104 nếu Script Block Logging được bật
#
# B. Atomic Red Team
#
# - T1204.002 User Execution: Malicious File
# - T1059.005 Visual Basic
#
# LƯU Ý:
# - Không chứa macro độc hại
# - Không download payload
# - Không C2
# - Không reverse shell
# - Không credential theft
#
# T1566.001 được mô phỏng ở mức artifact/email attachment.
# ==============================================================


WIN_HOST = "192.168.200.20"
WIN_USER = "ansible"
WIN_PASS = "131909"


# ==============================================================
# CONFIG
# ==============================================================

BASE_DIR = r"C:\Windows\Temp\atomic_kb01"

FAKE_DOC = (
    r"C:\Windows\Temp\atomic_kb01"
    r"\Invoice_2026.docm"
)

MARKER_FILE = (
    r"C:\Windows\Temp\atomic_kb01"
    r"\macro_execution_marker.log"
)


# ==============================================================
# WINRM
# ==============================================================

session = winrm.Session(
    f"http://{WIN_HOST}:5985/wsman",
    auth=(WIN_USER, WIN_PASS),
    transport="ntlm"
)


def run_cmd(cmd, label):

    print("\n" + "-" * 72)
    print(f"[*] {label}")
    print(f"    CMD: {cmd}")

    try:

        result = session.run_cmd(cmd)

        stdout = result.std_out.decode(
            "utf-8",
            errors="ignore"
        ).strip()

        stderr = result.std_err.decode(
            "utf-8",
            errors="ignore"
        ).strip()

        if result.status_code == 0:

            print("    [+] SUCCESS")

            if stdout:
                print("    [OUT]")
                print(stdout[:3000])

        else:

            print(
                f"    [-] FAILED: "
                f"{result.status_code}"
            )

            if stdout:
                print("[OUT]")
                print(stdout[:2000])

            if stderr:
                print("[ERR]")
                print(stderr[:2000])

        return result.status_code, stdout

    except Exception as e:

        print(f"    [!] Exception: {e}")

        return -1, ""


def run_ps(ps, label):

    encoded = base64.b64encode(
        ps.encode("utf-16le")
    ).decode()

    return run_cmd(
        "powershell.exe "
        "-NoProfile "
        f"-EncodedCommand {encoded}",
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
        "where winword.exe",
        "Check Microsoft Word"
    )

    run_ps(
        "Get-ExecutionPolicy -List",
        "Check PowerShell execution policy"
    )

    run_ps(
        """
        Get-Service WinDefend |
        Select-Object Status,Name
        """,
        "Check Windows Defender"
    )


# ==============================================================
# STEP 1
#
# T1566.001
#
# SPEARPHISHING ATTACHMENT - SIMULATION
#
# Không gửi email thật.
#
# Tạo một file .docm giả lập attachment.
# ==============================================================

def prepare_attachment():

    ps = f"""
    $dir = "{BASE_DIR}"
    $file = "{FAKE_DOC}"

    New-Item `
        -ItemType Directory `
        -Path $dir `
        -Force | Out-Null

    # Tạo file Office attachment giả lập.
    Set-Content `
        -Path $file `
        -Value "Atomic KB01 benign attachment simulation"

    Write-Host "Attachment created:"
    Write-Host $file
    """

    return run_ps(
        ps,
        "[1] T1566.001 - Prepare Spearphishing Attachment Artifact"
    )


# ==============================================================
# STEP 2
#
# T1204.002
#
# USER EXECUTION - MALICIOUS FILE
#
# Mở file bằng Microsoft Word nếu Word tồn tại.
#
# File KHÔNG chứa macro thực thi.
# ==============================================================

def open_attachment():

    ps = f"""
    $file = "{FAKE_DOC}"

    if (Test-Path $file) {{

        $word = Get-Command winword.exe `
            -ErrorAction SilentlyContinue

        if ($word) {{

            Write-Host "Launching Microsoft Word"

            Start-Process `
                "winword.exe" `
                -ArgumentList "`"$file`""

        }} else {{

            Write-Host "WINWORD.EXE not found"
        }}

    }} else {{

        Write-Host "Attachment not found"
    }}
    """

    return run_ps(
        ps,
        "[2] T1204.002 - User Opens Attachment"
    )


# ==============================================================
# STEP 3
#
# OFFICE TELEMETRY SIMULATION
#
# Mục đích:
#
# tạo marker thể hiện macro/content đã được kích hoạt.
#
# Không thực thi VBA.
# ==============================================================

def simulate_macro_execution():

    ps = f"""
    $marker = "{MARKER_FILE}"

    $message = @"
Atomic-KB01
Technique: T1059.005
Technique: T1204.002
Simulation: benign Office macro execution
Time: $(Get-Date)
User: $env:USERNAME
Host: $env:COMPUTERNAME
"@

    Add-Content `
        -Path $marker `
        -Value $message

    Write-Host "Benign macro execution marker created"
    """

    return run_ps(
        ps,
        "[3] T1059.005 - Simulated VBA Execution Marker"
    )


# ==============================================================
# STEP 4
#
# OFFICE -> POWERSHELL
#
# Đây là telemetry rất quan trọng để detection.
#
# Không sử dụng downloader.
# PowerShell chỉ ghi marker.
# ==============================================================

def generate_office_child_process_telemetry():

    ps = f"""
    $marker = "{MARKER_FILE}"

    $script = @"
Add-Content `
    -Path '{MARKER_FILE}' `
    -Value "Office-to-PowerShell simulation: $(Get-Date)"
"@

    $encoded = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes($script)
    )

    Start-Process `
        "powershell.exe" `
        -ArgumentList "-NoProfile -EncodedCommand $encoded"

    Write-Host "Benign PowerShell child process started"
    """

    return run_ps(
        ps,
        "[4] Generate Office -> PowerShell Telemetry"
    )


# ==============================================================
# STEP 5
#
# FILE CREATION
#
# Sysmon Event ID 11 nếu Sysmon FileCreate được bật.
# ==============================================================

def create_additional_artifacts():

    ps = f"""
    $dir = "{BASE_DIR}"

    $files = @(
        "macro_payload_stage1.txt",
        "office_execution.log",
        "download_simulation.txt"
    )

    foreach ($file in $files) {{

        $path = Join-Path $dir $file

        Set-Content `
            -Path $path `
            -Value "Benign Atomic KB01 artifact - $(Get-Date)"
    }}

    Write-Host "Artifacts created:"
    Get-ChildItem $dir
    """

    return run_ps(
        ps,
        "[5] Create Benign File Artifacts -> Sysmon Event ID 11"
    )


# ==============================================================
# STEP 6
#
# NETWORK TELEMETRY
#
# Chỉ kiểm tra DNS/HTTP capability.
#
# Không kết nối C2.
# ==============================================================

def network_precheck():

    ps = r"""
    Write-Host "===== NETWORK CHECK ====="

    Resolve-DnsName `
        "example.com" `
        -ErrorAction SilentlyContinue |
        Select-Object Name,Type,IPAddress

    Write-Host "Network check completed"
    """

    return run_ps(
        ps,
        "[6] Benign DNS Telemetry Check"
    )


# ==============================================================
# STEP 7
#
# ATOMIC RED TEAM CHECK
# ==============================================================

def atomic_check():

    ps = r'''
$ErrorActionPreference = "SilentlyContinue"

Write-Host "===== ATOMIC RED TEAM CHECK ====="

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
#
# ATOMIC T1204.002
#
# Chỉ hiển thị test trước.
#
# Không tự động chạy nếu chưa xác nhận
# nội dung Atomic test là benign.
# ==============================================================

def atomic_t1204():

    ps = r'''
$ErrorActionPreference = "Continue"

Write-Host "===== ATOMIC T1204.002 ====="

if (Get-Command Invoke-AtomicTest) {

    Invoke-AtomicTest `
        T1204.002 `
        -ShowDetailsBrief

} else {

    Write-Host "Invoke-AtomicTest unavailable"
}
'''

    return run_ps(
        ps,
        "[8] Atomic Red Team - T1204.002 - SHOW DETAILS"
    )


# ==============================================================
# STEP 9
#
# ATOMIC T1059.005
#
# Visual Basic / VBA
#
# ShowDetails để xác định test nào phù hợp
# với lab trước khi thực thi.
# ==============================================================

def atomic_t1059():

    ps = r'''
$ErrorActionPreference = "Continue"

Write-Host "===== ATOMIC T1059.005 ====="

if (Get-Command Invoke-AtomicTest) {

    Invoke-AtomicTest `
        T1059.005 `
        -ShowDetailsBrief

} else {

    Write-Host "Invoke-AtomicTest unavailable"
}
'''

    return run_ps(
        ps,
        "[9] Atomic Red Team - T1059.005 - SHOW DETAILS"
    )


# ==============================================================
# STEP 10
#
# VERIFY TELEMETRY ARTIFACTS
# ==============================================================

def verify_artifacts():

    ps = f"""
    Write-Host "===== KB01 ARTIFACTS ====="

    if (Test-Path "{BASE_DIR}") {{

        Get-ChildItem `
            "{BASE_DIR}" `
            -Force

    }} else {{

        Write-Host "Artifact directory not found"
    }}

    Write-Host ""
    Write-Host "===== MARKER CONTENT ====="

    if (Test-Path "{MARKER_FILE}") {{

        Get-Content "{MARKER_FILE}"

    }} else {{

        Write-Host "Marker not found"
    }}
    """

    return run_ps(
        ps,
        "[10] Verify KB01 Telemetry Artifacts"
    )


# ==============================================================
# STEP 11
#
# CLEANUP
# ==============================================================

def cleanup():

    ps = f"""
    if (Test-Path "{BASE_DIR}") {{

        Remove-Item `
            "{BASE_DIR}" `
            -Recurse `
            -Force

        Write-Host "KB01 artifacts removed"

    }} else {{

        Write-Host "Nothing to clean"
    }}
    """

    return run_ps(
        ps,
        "[11] Cleanup KB01 Artifacts"
    )


# ==============================================================
# MAIN
# ==============================================================

def main():

    print("=" * 72)

    print(
        "[*] KỊCH BẢN 01 - "
        "SPEARPHISHING ATTACHMENT / OFFICE MACRO"
    )

    print(f"[*] Target: {WIN_HOST}")

    print("=" * 72)

    precheck()

    time.sleep(2)

    prepare_attachment()

    time.sleep(2)

    open_attachment()

    time.sleep(5)

    simulate_macro_execution()

    time.sleep(2)

    generate_office_child_process_telemetry()

    time.sleep(4)

    create_additional_artifacts()

    time.sleep(2)

    network_precheck()

    time.sleep(2)

    atomic_check()

    time.sleep(2)

    atomic_t1204()

    time.sleep(2)

    atomic_t1059()

    time.sleep(2)

    verify_artifacts()

    print("\n" + "=" * 72)

    print("[✓] KB01 SIMULATION FINISHED")

    print("=" * 72)

    print("""
Expected telemetry:

[MITRE ATT&CK]

T1566.001
    Spearphishing Attachment
    -> simulated attachment artifact

T1204.002
    User Execution: Malicious File
    -> benign document opening simulation

T1059.005
    Command and Scripting Interpreter: Visual Basic
    -> Atomic Red Team details + benign marker

[Sysmon]

Event ID 1
    -> WINWORD.EXE
    -> powershell.exe

Event ID 11
    -> Office attachment creation
    -> marker/artifact creation

[PowerShell]

Event ID 4104
    -> nếu Script Block Logging được bật

[Artifact]

C:\\Windows\\Temp\\atomic_kb01\\
    Invoice_2026.docm
    macro_execution_marker.log
    macro_payload_stage1.txt
    office_execution.log
    download_simulation.txt

[Network]

DNS telemetry có thể xuất hiện nếu
network logging/Sysmon Event ID 22 được bật.

Không có:
    - payload download
    - C2
    - reverse shell
    - credential theft
    - ransomware
    """)


if __name__ == "__main__":
    main()
