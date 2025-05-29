#!/bin/bash

# Check if running with root privileges
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root, for example using sudo."
  exit 1
fi

# Get current EFI boot entries
BOOT_ENTRIES=$(efibootmgr | grep "^Boot" | grep -v "BootOrder")

# Check if there are any EFI boot entries
if [ -z "$BOOT_ENTRIES" ]; then
  echo "No EFI boot entries detected."
  exit 1
fi

# Display boot entries list
echo "Current EFI boot entries:"
echo "----------------------------------------"
echo "Index | BootNum | Description"
echo "----------------------------------------"

# Use array to store boot entry information
declare -a ENTRY_ARRAY
INDEX=1

while IFS= read -r line; do
  # Parse boot number and description
  BOOT_NUM=$(echo "$line" | awk '{print $1}' | sed 's/Boot\([0-9A-Fa-f]\+\)\*/\1/')
  DESCRIPTION=$(echo "$line" | cut -d '*' -f2 | sed 's/^ *//')
  
  # Skip currently used boot entry (BootCurrent)
  CURRENT_BOOT=$(efibootmgr | grep "BootCurrent" | awk '{print $2}')
  if [ "$BOOT_NUM" == "$CURRENT_BOOT" ]; then
    echo "$INDEX    | $BOOT_NUM   | $DESCRIPTION (currently in use)"
  else
    echo "$INDEX    | $BOOT_NUM   | $DESCRIPTION"
  fi
  
  # Store boot number in array
  ENTRY_ARRAY+=("$BOOT_NUM|$DESCRIPTION")
  INDEX=$((INDEX + 1))
done <<< "$BOOT_ENTRIES"

echo "----------------------------------------"

# Prompt user to enter boot entry numbers to delete (comma-separated)
echo "Enter the index numbers of boot entries to delete (e.g., 2,4,5), or press Enter to skip:"
read -p "Enter numbers: " INPUT

# Check if user provided any input
if [ -z "$INPUT" ]; then
  echo "No boot entries selected for deletion."
  exit 0
fi

# Parse the input numbers
IFS=',' read -ra SELECTION <<< "$INPUT"

# Iterate through selected numbers and delete corresponding boot entries
for NUM in "${SELECTION[@]}"; do
  # Remove possible spaces
  NUM=$(echo "$NUM" | tr -d ' ')
  
  # Check if input is a number
  if ! [[ "$NUM" =~ ^[0-9]+$ ]]; then
    echo "Invalid number: $NUM. Please ensure you enter numbers only."
    continue
  fi
  
  # Check if number is within range
  if [ "$NUM" -lt 1 ] || [ "$NUM" -gt "${#ENTRY_ARRAY[@]}" ]; then
    echo "Number $NUM is out of range."
    continue
  fi
  
  # Get corresponding boot number and description
  ENTRY="${ENTRY_ARRAY[$((NUM-1))]}"
  BOOT_NUM=$(echo "$ENTRY" | cut -d '|' -f1)
  DESCRIPTION=$(echo "$ENTRY" | cut -d '|' -f2)
  
  # Check if this is the currently used boot entry
  CURRENT_BOOT=$(efibootmgr | grep "BootCurrent" | awk '{print $2}')
  if [ "$BOOT_NUM" == "$CURRENT_BOOT" ]; then
    echo "Skipping deletion of currently used boot entry: $DESCRIPTION (Boot$BOOT_NUM)"
    continue
  fi
  
  # Delete boot entry
  echo "Deleting boot entry: $DESCRIPTION (Boot$BOOT_NUM)..."
  efibootmgr -b "$BOOT_NUM" -B
  
  if [ $? -eq 0 ]; then
    echo "Successfully deleted boot entry: $DESCRIPTION (Boot$BOOT_NUM)"
  else
    echo "Failed to delete boot entry: $DESCRIPTION (Boot$BOOT_NUM)"
  fi
done

echo "Operation completed. It's recommended to reboot the system to apply changes."
