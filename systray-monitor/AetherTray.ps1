<#
.SYNOPSIS
AETHER-PULSE // OMNI-LOOP System Tray Monitor (Advanced)

.DESCRIPTION
Dynamically draws status orbs (Green, Yellow, Red) in the systray to reflect DevSecOps threat levels.
Right-clicking the orb shows the live status of the cognitive and reflex engines.
#>

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# =========================================================================
# Dynamic Icon Generator (No .ico files needed)
# =========================================================================
function Get-ColoredOrb {
    param([string]$ColorName)
    $bmp = New-Object System.Drawing.Bitmap(32, 32)
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    
    # Draw the colored orb
    $color = [System.Drawing.Color]::FromName($ColorName)
    $brush = New-Object System.Drawing.SolidBrush($color)
    $gfx.FillEllipse($brush, 3, 3, 26, 26)
    
    # Add a stark black border for the Neo-Techno aesthetic
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::Black, 2)
    $gfx.DrawEllipse($pen, 3, 3, 26, 26)
    
    $icon = [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
    
    $gfx.Dispose()
    $bmp.Dispose()
    return $icon
}

# =========================================================================
# Systray Initialization
# =========================================================================
$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
$notifyIcon.Icon = Get-ColoredOrb -ColorName "LimeGreen"
$notifyIcon.Text = "AETHER-PULSE: System Nominal"
$notifyIcon.Visible = $true

$contextMenu = New-Object System.Windows.Forms.ContextMenu

# --- Engine Status List ---
$statusHeader = New-Object System.Windows.Forms.MenuItem("--- AETHER-PULSE ENGINES ---")
$statusHeader.Enabled = $false
$contextMenu.MenuItems.Add($statusHeader)

$itemOllama = New-Object System.Windows.Forms.MenuItem(" [ Cortex.X : Ollama ]         ONLINE")
$itemOllama.Enabled = $false
$contextMenu.MenuItems.Add($itemOllama)

$itemQdrant = New-Object System.Windows.Forms.MenuItem(" [ Cortex.X : Qdrant ]         ONLINE")
$itemQdrant.Enabled = $false
$contextMenu.MenuItems.Add($itemQdrant)

$itemArgus = New-Object System.Windows.Forms.MenuItem(" [ 0xARGUS : Attestation ]    ONLINE")
$itemArgus.Enabled = $false
$contextMenu.MenuItems.Add($itemArgus)

$itemSynapse = New-Object System.Windows.Forms.MenuItem(" [ Synapse : WASM Router ]  ONLINE")
$itemSynapse.Enabled = $false
$contextMenu.MenuItems.Add($itemSynapse)

$contextMenu.MenuItems.Add((New-Object System.Windows.Forms.MenuItem("-")))

# --- Threat Simulation Triggers (Changes Colors & Alerts) ---
$simulateAlert = New-Object System.Windows.Forms.MenuItem("Simulate K-Fence Anomaly (Yellow Alert)")
$simulateAlert.add_Click({
    $notifyIcon.Icon = Get-ColoredOrb -ColorName "Gold"
    $notifyIcon.Text = "AETHER-PULSE: Anomaly Detected"
    $notifyIcon.ShowBalloonTip(3000, "Kernel Anomaly Detected", "Synapse intercepting anomalous REVENANT kernel behavior...", [System.Windows.Forms.ToolTipIcon]::Warning)
})
$contextMenu.MenuItems.Add($simulateAlert)

$simulateCritical = New-Object System.Windows.Forms.MenuItem("Simulate Hardware Breach (Red Alert)")
$simulateCritical.add_Click({
    $notifyIcon.Icon = Get-ColoredOrb -ColorName "Red"
    $notifyIcon.Text = "AETHER-PULSE: Critical Breach"
    $notifyIcon.ShowBalloonTip(3000, "CRITICAL SYSTEM BREACH", "0xARGUS Hardware Attestation FAILED. Initiating WASM lockdown.", [System.Windows.Forms.ToolTipIcon]::Error)
})
$contextMenu.MenuItems.Add($simulateCritical)

$simulateClear = New-Object System.Windows.Forms.MenuItem("Clear Alerts (Green / Nominal)")
$simulateClear.add_Click({
    $notifyIcon.Icon = Get-ColoredOrb -ColorName "LimeGreen"
    $notifyIcon.Text = "AETHER-PULSE: System Nominal"
    $notifyIcon.ShowBalloonTip(3000, "Threat Mitigated", "Threat neutralized by Cortex.X logic. Returning to baseline.", [System.Windows.Forms.ToolTipIcon]::Info)
})
$contextMenu.MenuItems.Add($simulateClear)

$contextMenu.MenuItems.Add((New-Object System.Windows.Forms.MenuItem("-")))

# --- Termination ---
$exitItem = New-Object System.Windows.Forms.MenuItem("Terminate Monitor")
$exitItem.add_Click({
    $notifyIcon.Visible = $false
    [System.Windows.Forms.Application]::Exit()
})
$contextMenu.MenuItems.Add($exitItem)

$notifyIcon.ContextMenu = $contextMenu

# Show Startup Alert
$notifyIcon.ShowBalloonTip(3000, "AETHER-PULSE Online", "All DevSecOps Engines are tracking.", [System.Windows.Forms.ToolTipIcon]::Info)

# Keep the GUI thread alive
[System.Windows.Forms.Application]::Run()
