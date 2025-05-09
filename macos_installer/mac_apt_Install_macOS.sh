#!/bin/bash
# mac_apt Installation Script for macOS - Version 2.6
# Author: Zachary Burnham (@zmbf0r3ns1cs), Yogesh Khatri (@swiftforensics)
#------------------------------------------------------------------------------
# Script to auto-download Yogesh Khatri's mac_apt tool from GitHub (with necessary 
# dependencies) and install https://github.com/ydkhatri/mac_apt 

# Run as './mac_apt_Install_macOS.sh'

PYTHONVER="python3.13"

# Define function to verify validity of user directory input
verifyDir () {
    cd $userDir &> /tmp/mac_apt_installer_output.txt || mkdir $userDir &> /tmp/mac_apt_installer_output.txt
    if [[ $? -ne 0 ]]; then
        echo "[!] Invalid directory. Please try again."
        # Bring user back to beginning to correct directory syntax
        chooseInstallation_Dir
    else 
        # Desired user directory is valid
        echo "[~] Installing mac_apt to $userDir..."
    fi
}

# Define function for user input for desired installation directory
chooseInstallation_Dir () {
    read -p "[*] Would you like to specify an installation directory? [Y/n] " userDecision
    # Verify user input
    if [[ $userDecision = "Y" ]] || [[ $userDecision = "y" ]]; then
        echo "[~] EX: /Users/<username>/Desktop"
        read -p "Directory Path: " userDir
        # Verify if valid directory
        verifyDir
    elif [[ $userDecision = "N" ]] || [[ $userDecision = "n" ]]; then
        # Set $userDir to user's current directory
        export userDir=`pwd`
        echo "[~] Installing mac_apt to $userDir..."
    else
        # Bring user back to beginning if y or n not specified
        echo "[!] Invalid response. Please try again."
        chooseInstallation_Dir
    fi 
}

# ----------------------------------------------------------------------------------- #
# ------------------------ MAIN BODY OF SCRIPT BEGINS HERE -------------------------- #
# ----------------------------------------------------------------------------------- #

echo "" # Space for script legibility
echo "[*] mac_apt Installation Script for macOS - Version 2.6"
echo "-----------------------------------------------------------"

# Print macOS version
echo -n "[*] macOS version is "
sw_vers -productversion
sw_vers -productversion &> /tmp/mac_apt_installer_output.txt

# Print processor architecture (ARM/x64)
echo -n "[*] architecture is "
uname -m
uname -a &> /tmp/mac_apt_installer_output.txt

# Prompt user to choose default installation or custom directory
chooseInstallation_Dir

# Check for Homebrew, install if not found
if test ! $(which brew); then
    echo "[+] Installing homebrew..."
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)" </dev/null &> /tmp/mac_apt_installer_output.txt
    # Check for successful install
    if [[ $? -ne 0 ]]; then
        echo "[!] Installation of Homebrew failed due to an error."
        echo "[!] Please report this to the developer. Send /tmp/mac_apt_installer_output.txt"
        exit 1; 
    fi
fi

# Ensure Homebrew is up-to-date
echo "[~] Ensuring Homebrew is up-to-date..."
brew update &> /tmp/mac_apt_installer_output.txt

# Check for specfic python version, install if not found
if which "$PYTHONVER" > /dev/null 2>&1; then
    echo "[*] $PYTHONVER is already installed"
else
    echo "[+] Installing $PYTHONVER..."
    brew install "${PYTHONVER/python/python@}" git &> /tmp/mac_apt_installer_output.txt
    # Check for successful install
    if [[ $? -ne 0 ]]; then
        echo "[!] Installation of $PYTHONVER failed due to an error."
        echo "[!] Please report this to the developer. Send /tmp/mac_apt_installer_output.txt"
        exit 1; 
    fi
fi

# Download mac_apt from GitHub to Desktop
echo "[+] Downloading mac_apt from GitHub..."
cd $userDir
git clone --recursive https://github.com/ydkhatri/mac_apt.git &> /tmp/mac_apt_installer_output.txt
# Ensure download is successful
if [[ $? -ne 0 ]]; then
    echo "[!] mac_apt download failed due to 'git clone' error."
    echo "[!] Please delete the exiting 'mac_apt' folder and try again!"
#    echo "[!] Please report this to the developer."
    exit 1; 
fi

cd mac_apt
echo "[+] Creating virtual environment with virtualenv..."
$PYTHONVER -m venv env &> /tmp/mac_apt_installer_output.txt

# Activate env with virtualenv to install within virtual environment
source env/bin/activate

# Install dependencies
echo "[+] Installing dependencies...this may take a few minutes..."
pip3 install pybindgen==0.21.0 --no-cache-dir &> /tmp/mac_apt_installer_output.txt
pip3 install -r requirements.txt --no-cache-dir &> /tmp/mac_apt_installer_output.txt
if [[ $? -ne 0 ]]; then
    echo "[!] Installation of one or more required dependencies has failed."
    echo "[!] Please report this to the developer. Send /tmp/mac_apt_installer_output.txt"
    exit 1; 
fi

echo "[*] mac_apt successfully downloaded and installed!"
echo "------------------------------------------------------------------------------"

echo " To run mac_apt, you will have to go to the mac_apt folder in Terminal"
echo " and then enter the virtual environment using the following command "
echo "   source env/bin/activate "
echo " Then run mac_apt as you would normally "
echo "   python3 mac_apt.py ...."
echo " "
echo " When finished, exit the virtual environment using the command"
echo "   deactivate"