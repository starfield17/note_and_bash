#!/bin/bash

# Ensure the script runs with root privileges
if [[ $EUID -ne 0 ]]; then
   echo "Please run this script as root."
   exit 1
fi

# Configuration variables
GRUB_CFG_PATH="/boot/grub2/grub.cfg"       # For BIOS systems
# GRUB_CFG_PATH="/boot/efi/EFI/rocky/grub.cfg" # For UEFI systems, uncomment as needed

# Backup current grub.cfg
BACKUP_PATH="/boot/grub2/grub.cfg.backup_$(date +%F_%T)"
cp "$GRUB_CFG_PATH" "$BACKUP_PATH"
if [[ $? -ne 0 ]]; then
    echo "Failed to backup grub.cfg, please check permissions and path."
    exit 1
fi
echo "grub.cfg backed up to $BACKUP_PATH"

# Get all menuentries
mapfile -t MENU_ENTRIES < <(grep "^menuentry" "$GRUB_CFG_PATH" | cut -d "'" -f2)

if [[ ${#MENU_ENTRIES[@]} -eq 0 ]]; then
    echo "No GRUB boot entries found."
    exit 1
fi

echo "Current GRUB boot entries:"
echo "----------------------------------"
for i in "${!MENU_ENTRIES[@]}"; do
    echo "$((i+1)). ${MENU_ENTRIES[$i]}"
done
echo "----------------------------------"

# Prompt user to select entries to delete (multiple entries allowed, separated by space or comma)
read -p "Enter the numbers of boot entries to delete (space/comma separated, press Enter to skip): " INPUT

# Exit if no input provided
if [[ -z "$INPUT" ]]; then
    echo "No entries selected, script exiting."
    exit 0
fi

# Process user input - replace commas with spaces and convert to array
INPUT=$(echo "$INPUT" | tr ',' ' ')
read -a DELETE_NUMBERS <<< "$INPUT"

# Declare associative array to store entries to delete
declare -A DELETE_ENTRIES

# Validate input numbers
for num in "${DELETE_NUMBERS[@]}"; do
    if ! [[ "$num" =~ ^[0-9]+$ ]]; then
        echo "Invalid number: $num, please enter numeric values."
        exit 1
    fi
    if (( num < 1 || num > ${#MENU_ENTRIES[@]} )); then
        echo "Number $num is out of range, please enter between 1 and ${#MENU_ENTRIES[@]}."
        exit 1
    fi
    # Store entries to delete, preventing duplicates
    DELETE_ENTRIES["$num"]=1
done

# Confirm deletion
echo "You have selected to delete the following boot entries:"
for num in "${!DELETE_ENTRIES[@]}"; do
    echo "$num. ${MENU_ENTRIES[$((num-1))]}"
done
read -p "Are you sure you want to delete these entries? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 0
fi

# Process each entry marked for deletion
for num in "${!DELETE_ENTRIES[@]}"; do
    ENTRY="${MENU_ENTRIES[$((num-1))]}"
    echo "Processing deletion of boot entry: $ENTRY"

    # Determine entry type
    if [[ "$ENTRY" == Rocky* ]]; then
        # Assuming Rocky Linux snapshot naming format: "Rocky Linux (snapshotX)"
        SNAPSHOT_NAME=$(echo "$ENTRY" | grep -oP '(?<=Rocky Linux ).*')
        # Extract snapshot name, remove parentheses
        SNAPSHOT_NAME=$(echo "$SNAPSHOT_NAME" | tr -d '()')
        
        # Assuming Btrfs with snapshots in /@snapshots
        SNAPSHOT_PATH="/@snapshots/$SNAPSHOT_NAME"
        
        # Check if snapshot exists
        if sudo btrfs subvolume list / | grep -q "$SNAPSHOT_PATH"; then
            echo "Deleting snapshot: $SNAPSHOT_PATH"
            sudo btrfs subvolume delete "$SNAPSHOT_PATH"
            if [[ $? -ne 0 ]]; then
                echo "Failed to delete snapshot $SNAPSHOT_PATH, please check manually."
            else
                echo "Snapshot deleted: $SNAPSHOT_PATH"
            fi
        else
            echo "Snapshot $SNAPSHOT_PATH not found, please check manually."
        fi
    elif [[ "$ENTRY" == Windows* ]]; then
        echo "Windows boot entry detected. Will remove this entry from GRUB configuration."
        # Windows entries are usually auto-detected by os-prober, manual deletion not recommended
        # If deletion is needed, disable os-prober or manually edit grub.cfg (not recommended)
        echo "Note: Removing Windows boot entries may require additional configuration. Proceed with caution."
        # No actual deletion performed here
    else
        echo "Unknown boot entry type: $ENTRY. Skipping deletion."
    fi
    echo "----------------------------------"
done

# Update GRUB configuration
echo "Updating GRUB configuration..."
if [[ "$GRUB_CFG_PATH" == "/boot/grub2/grub.cfg" ]]; then
    grub2-mkconfig -o /boot/grub2/grub.cfg
elif [[ "$GRUB_CFG_PATH" == "/boot/efi/EFI/rocky/grub.cfg" ]]; then
    grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg
else
    echo "Unknown GRUB configuration path, please update GRUB manually."
    exit 1
fi

if [[ $? -ne 0 ]]; then
    echo "Failed to update GRUB configuration."
    exit 1
fi

echo "GRUB configuration updated successfully."

# Reboot prompt
echo "Operation complete. A system reboot is recommended to apply changes."
read -p "Reboot now? (y/N): " REBOOT_CONFIRM
if [[ "$REBOOT_CONFIRM" =~ ^[Yy]$ ]]; then
    reboot
else
    echo "Please reboot manually to apply changes."
fi
