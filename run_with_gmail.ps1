param(
    [string]$SenderAddress,
    [string]$ServerAddress = '127.0.0.1:8000'
)

$ErrorActionPreference = 'Stop'
$servinnPython = Join-Path $PSScriptRoot 'env\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $servinnPython)) {
    throw 'The project Python environment is missing: env\Scripts\python.exe.'
}
if (-not $SenderAddress) {
    $SenderAddress = Read-Host 'Gmail sender address (for example, yourname@gmail.com)'
}
$SenderAddress = $SenderAddress.Trim()
if ($SenderAddress -notmatch '^[^\s@]+@gmail\.com$') {
    throw 'Enter the @gmail.com address that owns the Gmail App Password.'
}

Write-Host 'Use a Gmail App Password, not your normal Google password.'
Write-Host 'Create one at https://myaccount.google.com/apppasswords after enabling 2-Step Verification.'
Write-Host 'This is the 16-character App Password from Google, not the 6-digit SERVINN email code.'
Write-Host 'Spaces between the four groups are accepted. Leave the input empty to cancel.'
$servinnMailSecret = $null
$servinnCandidatePassword = $null
for ($servinnAttempt = 0; $servinnAttempt -lt 3; $servinnAttempt++) {
    $servinnMailSecret = Read-Host 'Gmail App Password (input is hidden)' -AsSecureString
    $servinnCandidatePassword = ([System.Net.NetworkCredential]::new('', $servinnMailSecret).Password -replace '\s', '')
    if ($servinnCandidatePassword.Length -eq 16) { break }
    $servinnMailSecret.Dispose()
    $servinnMailSecret = $null
    if ($servinnCandidatePassword.Length -eq 0) {
        $servinnCandidatePassword = $null
        Write-Host 'Setup cancelled. No email settings were changed.'
        return
    }
    $servinnCandidatePassword = $null
    Write-Host 'That entry is not a 16-character Gmail App Password. Copy the App Password from Google and try again.' -ForegroundColor Yellow
}
if (-not $servinnMailSecret) {
    Write-Host 'Setup stopped. Create a Gmail App Password at https://myaccount.google.com/apppasswords, then run this script again.' -ForegroundColor Yellow
    return
}
$servinnPreviousMail = @{}
foreach ($servinnKey in @('EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'EMAIL_HOST', 'EMAIL_PORT', 'DEFAULT_FROM_EMAIL')) {
    $servinnPreviousMail[$servinnKey] = [Environment]::GetEnvironmentVariable($servinnKey, 'Process')
}

Push-Location -LiteralPath $PSScriptRoot
try {
    $env:EMAIL_HOST_USER = $SenderAddress
    $env:EMAIL_HOST_PASSWORD = $servinnCandidatePassword
    $servinnCandidatePassword = $null
    $env:EMAIL_HOST = 'smtp.gmail.com'
    $env:EMAIL_PORT = '587'
    $env:DEFAULT_FROM_EMAIL = $SenderAddress

    & $servinnPython manage.py check_email
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Gmail connection failed. Correct the issue above and run this script again.' -ForegroundColor Yellow
        return
    }
    Write-Host 'Starting SERVINN. Keep this terminal open; press Ctrl+C to stop.'
    & $servinnPython manage.py runserver $ServerAddress
}
catch {
    Write-Host 'Unable to start SERVINN with Gmail. Check the project environment and try again.' -ForegroundColor Red
}
finally {
    foreach ($servinnKey in $servinnPreviousMail.Keys) {
        [Environment]::SetEnvironmentVariable($servinnKey, $servinnPreviousMail[$servinnKey], 'Process')
    }
    $servinnMailSecret.Dispose()
    $servinnCandidatePassword = $null
    $servinnPreviousMail.Clear()
    Pop-Location
}
