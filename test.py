import winrm

session = winrm.Session(
    'http://192.168.200.20:5985/wsman',
    auth=('ansible', '19092005'),
    transport='ntlm'
)

r = session.run_cmd('whoami')

print(r.status_code)
print(r.std_out.decode())
print(r.std_err.decode())
