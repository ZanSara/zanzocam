# How to re-create the image

### Create the base image and boot

This steps gives you a SD card that can connect to your WiFi network, so that you can control it through SSH. This is necessary for the later steps. You might want to delete your network information at the end of the process.

- Download latest RPI OS [here](https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2020-12-04/2020-12-02-raspios-buster-armhf-lite.zip)
- Unzip it
- Flash onto SD:
    - `dd if=nome-immagine.img of=/dev/sdX bs=4M status=progress oflag=sync` with `sudo`
- Add empty `ssh` file in the `boot` partition 
- Add `config.txt` file in the `boot` partition
    - Content:
```
# Disable the rainbow splash screen
disable_splash=1

# No boot delay
boot_delay=0

# Disable the LED
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on

# Enable camera
start_x=1             # essential
gpu_mem=128           # at least, or maybe more if you wish
disable_camera_led=1  # optional, if you don't want the led to glow
```
- Change `/etc/wpa_supplicant/wpa_supplicant.conf` on `rootfs` with your local wifi data
    - Example content:
```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=IT

network={
    ssid="SSIDNAME"
    psk="PASSWORD"
}
```
- Boot the RPI with the SD card
- Find its IP with `nmap -p 22 192.168.1.0/24` 
- Connect to it with SSH: `ssh pi@192.168.1.xxx`


### Basic setup (libraries and configuration)

This step installs a few libraries required for the webcam to work.

- Switch from the `pi` user to `zanzocam-bot`:
    - Create user with home directory: `sudo useradd -m zanzocam-bot`
    - Change password: `sudo passwd zanzocam-bot`
    - Make sudoer: `sudo usermod -aG sudo zanzocam-bot`
    - Allow passwordless `sudo` for `zanzocam-bot`: `sudo nano /etc/sudoers`
          - Add ad the end: `zanzocam-bot ALL=(ALL:ALL) NOPASSWD:ALL`
    - Allow `zanzocam-bot` to access the webcam: `sudo usermod -aG video zanzocam-bot`

    - Leave the SSH connection and reconnect with `zanzocam-bot`
    - Lock `pi`:  `sudo passwd -l pi`
    - Kill all processes (shold be none): `sudo pkill -KILL -u pi`
    - Remove the user: `sudo deluser --remove-home pi`
    
- Generate locales:
    - Get rid of useless env vars: `unset $(awk 'BEGIN{for(v in ENVIRON) print v}' | grep "LC")`
    - Uncomment the IT locale in the proper file:  `sudo perl -pi -e 's/# it_IT.UTF-8 UTF-8/it_IT.UTF-8 UTF-8/g' /etc/locale.gen`
    - Generate locales: `sudo locale-gen it_IT.UTF-8`
    - Update locales: `sudo update-locale it_IT.UTF-8`
    
- Create alias for `ll` in `~/.bashrc`: `nano ~/.bashrc`
    - Add at the end: `alias ll="ls -lah"`
- Update the index: `sudo apt update`
- Install utilities, graphics libraries, fonts: `sudo apt install -y git whois libopenjp2-7-dev libtiff-dev fonts-dejavu`
- Set timezone: `sudo timedatectl set-timezone Europe/Rome`
- Setup cronjob to turn off HDMI at reboot:
    - `sudo nano /etc/cron.d/no-hdmi`
    - Content:
```
# Disable the HDMI port (to save power)
@reboot /usr/bin/tvservice -o
```
- Install pip3 and venv: `sudo apt install -y python3-pip python3-venv`
- Clone the Zanzocam repo into the home: `git clone https://github.com/ZanSara/zanzocam.git`
- Copy out the `webcam` folder: `cp -R zanzocam/webcam .`
- Copy the `setup-server` folder into `/var/www`: `sudo cp -r ~/zanzocam/setup-server /var/www`
- Change ownership of the `setup-server` folder to `zanzocam-bot`: `sudo chown zanzocam-bot:zanzocam-bot /var/www/setup-server`
- Enter the webcam folder: `cd webcam`
- Create venv: `python3 -m venv venv`
- Activate venv: `source venv/bin/activate`
- Install the requirements: `pip install -r requirements.txt`
- Leave venv: `deactivate`


### Setup the autohotspot feature

This step makes the RPI able to generate its own WiFi network (SSID: zanzocam-setup, Password: webcam) when no known WiFi network is detected.

Instructions found [here](https://www.raspberryconnect.com/projects/65-raspberrypi-hotspot-accesspoints/158-raspberry-pi-auto-wifi-hotspot-switch-direct-connection)

- Install `hostapd` and `dnsmasq`
    - `sudo apt install -y hostapd dnsmasq`
- `hostapd` and `dnsmasq` run when the Raspberry is started, but they should only start if the home router is not found. So automatic startup needs to be disabled and `hostapd` needs to be unmasked:
    - `sudo systemctl unmask hostapd`
    - `sudo systemctl disable hostapd`
    - `sudo systemctl disable dnsmasq`
- Edit `hostapd` configuration file to create a network called `zaozocam-setup` and password `webcamdelrifugio`:
    - `sudo nano /etc/hostapd/hostapd.conf`
    - Content:
```
# 2.4GHz setup wifi 80211 b,g,n
interface=wlan0
driver=nl80211
ssid=zanzocam-setup
hw_mode=g
channel=8
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=webcamdelrifugio
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP TKIP
rsn_pairwise=CCMP

# 80211n
country_code=IT
ieee80211n=1
ieee80211d=1
```    
- Edit `hostapd` defaults
    - `sudo nano /etc/default/hostapd`
    - Change `#DAEMON_CONF=""` into `DAEMON_CONF="/etc/hostapd/hostapd.conf"`
    - Check that `DAEMON_OPTS=""` is preceded by a `#`, so that the line reads `#DAEMON_OPTS=""`
- Edit `dnsmasq` configuration:
    - `sudo nano /etc/dnsmasq.conf`
    - Add at the bottom:
```
#AutoHotspot Config
#stop DNSmasq from using resolv.conf
no-resolv
#Interface to use
interface=wlan0
bind-interfaces
dhcp-range=10.0.0.50,10.0.0.150,12h
```
- Modify the `interfaces` file:
    - `sudo nano /etc/network/interfaces`
    - Must be equal to:
```
# interfaces(5) file used by ifup(8) and ifdown(8) 

# Please note that this file is written to be used with dhcpcd 
# For static IP, consult /etc/dhcpcd.conf and 'man dhcpcd.conf' 

# Include files from /etc/network/interfaces.d: 
source-directory /etc/network/interfaces.d 
```
- Stop `dhcpcd` from starting the wifi network, so that the `autohotspot` script in the next step can work:
    - `sudo nano /etc/dhcpcd.conf`
    - Add at the bottom: `nohook wpa_supplicant`
- Create a service which will run the autohotspot script when the Raspberry Pi starts up
    - `sudo nano /etc/systemd/system/autohotspot.service`
    - Content:
```
[Unit]
Description=Automatically generates an hotspot when a valid ssid is not in range
After=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/autohotspot

[Install]
WantedBy=multi-user.target
```
- Enable the service:
    - `sudo systemctl enable autohotspot.service`
- Create the `autohotspot` script:
    - `sudo nano /usr/bin/autohotspot`
    - Content:
```
#!/bin/bash
#version 0.961-N/HS

#You may share this script on the condition a reference to RaspberryConnect.com 
#must be included in copies or derivatives of this script. 

#A script to switch between a wifi network and a non internet routed Hotspot
#Works at startup or with a seperate timer or manually without a reboot
#Other setup required find out more at
#http://www.raspberryconnect.com

wifidev="wlan0" #device name to use. Default is wlan0.
#use the command: iw dev ,to see wifi interface name 

IFSdef=$IFS
cnt=0
#These four lines capture the wifi networks the RPi is setup to use
wpassid=$(awk '/ssid="/{ print $0 }' /etc/wpa_supplicant/wpa_supplicant.conf | awk -F'ssid=' '{ print $2 }' | sed 's/\r//g'| awk 'BEGIN{ORS=","} {print}' | sed 's/\"/''/g' | sed 's/,$//')
IFS=","
ssids=($wpassid)
IFS=$IFSdef #reset back to defaults


#Note:If you only want to check for certain SSIDs
#Remove the # in in front of ssids=('mySSID1'.... below and put a # infront of all four lines above
# separated by a space, eg ('mySSID1' 'mySSID2')
#ssids=('mySSID1' 'mySSID2' 'mySSID3')

#Enter the Routers Mac Addresses for hidden SSIDs, seperated by spaces ie 
#( '11:22:33:44:55:66' 'aa:bb:cc:dd:ee:ff' ) 
mac=()

ssidsmac=("${ssids[@]}" "${mac[@]}") #combines ssid and MAC for checking

createAdHocNetwork()
{
    echo "Creating Hotspot"
    ip link set dev "$wifidev" down
    ip a add 10.0.0.5/24 brd + dev "$wifidev"
    ip link set dev "$wifidev" up
    dhcpcd -k "$wifidev" >/dev/null 2>&1
    systemctl start dnsmasq
    systemctl start hostapd
}

KillHotspot()
{
    echo "Shutting Down Hotspot"
    ip link set dev "$wifidev" down
    systemctl stop hostapd
    systemctl stop dnsmasq
    ip addr flush dev "$wifidev"
    ip link set dev "$wifidev" up
    dhcpcd  -n "$wifidev" >/dev/null 2>&1
}

ChkWifiUp()
{
	echo "Checking WiFi connection ok"
        sleep 20 #give time for connection to be completed to router
	if ! wpa_cli -i "$wifidev" status | grep 'ip_address' >/dev/null 2>&1
        then #Failed to connect to wifi (check your wifi settings, password etc)
	       echo 'Wifi failed to connect, falling back to Hotspot.'
               wpa_cli terminate "$wifidev" >/dev/null 2>&1
	       createAdHocNetwork
	fi
}


chksys()
{
    #After some system updates hostapd gets masked using Raspbian Buster, and above. This checks and fixes  
    #the issue and also checks dnsmasq is ok so the hotspot can be generated.
    #Check Hostapd is unmasked and disabled
    if systemctl -all list-unit-files hostapd.service | grep "hostapd.service masked" >/dev/null 2>&1 ;then
	systemctl unmask hostapd.service >/dev/null 2>&1
    fi
    if systemctl -all list-unit-files hostapd.service | grep "hostapd.service enabled" >/dev/null 2>&1 ;then
	systemctl disable hostapd.service >/dev/null 2>&1
	systemctl stop hostapd >/dev/null 2>&1
    fi
    #Check dnsmasq is disabled
    if systemctl -all list-unit-files dnsmasq.service | grep "dnsmasq.service masked" >/dev/null 2>&1 ;then
	systemctl unmask dnsmasq >/dev/null 2>&1
    fi
    if systemctl -all list-unit-files dnsmasq.service | grep "dnsmasq.service enabled" >/dev/null 2>&1 ;then
	systemctl disable dnsmasq >/dev/null 2>&1
	systemctl stop dnsmasq >/dev/null 2>&1
    fi
}


FindSSID()
{
#Check to see what SSID's and MAC addresses are in range
ssidChk=('NoSSid')
i=0; j=0
until [ $i -eq 1 ] #wait for wifi if busy, usb wifi is slower.
do
        ssidreply=$((iw dev "$wifidev" scan ap-force | egrep "^BSS|SSID:") 2>&1) >/dev/null 2>&1 
        #echo "SSid's in range: " $ssidreply
	printf '%s\n' "${ssidreply[@]}"
        echo "Device Available Check try " $j
        if (($j >= 10)); then #if busy 10 times goto hotspot
                 echo "Device busy or unavailable 10 times, going to Hotspot"
                 ssidreply=""
                 i=1
	elif echo "$ssidreply" | grep "No such device (-19)" >/dev/null 2>&1; then
                echo "No Device Reported, try " $j
		NoDevice
        elif echo "$ssidreply" | grep "Network is down (-100)" >/dev/null 2>&1 ; then
                echo "Network Not available, trying again" $j
                j=$((j + 1))
                sleep 2
	elif echo "$ssidreply" | grep "Read-only file system (-30)" >/dev/null 2>&1 ; then
		echo "Temporary Read only file system, trying again"
		j=$((j + 1))
		sleep 2
	elif echo "$ssidreply" | grep "Invalid exchange (-52)" >/dev/null 2>&1 ; then
		echo "Temporary unavailable, trying again"
		j=$((j + 1))
		sleep 2
	elif echo "$ssidreply" | grep -v "resource busy (-16)"  >/dev/null 2>&1 ; then
               echo "Device Available, checking SSid Results"
		i=1
	else #see if device not busy in 2 seconds
                echo "Device unavailable checking again, try " $j
		j=$((j + 1))
		sleep 2
	fi
done

for ssid in "${ssidsmac[@]}"
do
     if (echo "$ssidreply" | grep -F -- "$ssid") >/dev/null 2>&1
     then
	      #Valid SSid found, passing to script
              echo "Valid SSID Detected, assesing Wifi status"
              ssidChk=$ssid
              return 0
      else
	      #No Network found, NoSSid issued"
              echo "No SSid found, assessing WiFi status"
              ssidChk='NoSSid'
     fi
done
}

NoDevice()
{
	#if no wifi device,ie usb wifi removed, activate wifi so when it is
	#reconnected wifi to a router will be available
	echo "No wifi device connected"
	wpa_supplicant -B -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1
	exit 1
}

chksys
FindSSID

#Create Hotspot or connect to valid wifi networks
if [ "$ssidChk" != "NoSSid" ] 
then
       if systemctl status hostapd | grep "(running)" >/dev/null 2>&1
       then #hotspot running and ssid in range
              KillHotspot
              echo "Hotspot Deactivated, Bringing Wifi Up"
              wpa_supplicant -B -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1
              ChkWifiUp
       elif { wpa_cli -i "$wifidev" status | grep 'ip_address'; } >/dev/null 2>&1
       then #Already connected
              echo "Wifi already connected to a network"
       else #ssid exists and no hotspot running connect to wifi network
              echo "Connecting to the WiFi Network"
              wpa_supplicant -B -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1
              ChkWifiUp
       fi
else #ssid or MAC address not in range
       if systemctl status hostapd | grep "(running)" >/dev/null 2>&1
       then
              echo "Hostspot already active"
       elif { wpa_cli status | grep "$wifidev"; } >/dev/null 2>&1
       then
              echo "Cleaning wifi files and Activating Hotspot"
              wpa_cli terminate >/dev/null 2>&1
              ip addr flush "$wifidev"
              ip link set dev "$wifidev" down
              rm -r /var/run/wpa_supplicant >/dev/null 2>&1
              createAdHocNetwork
       else #"No SSID, activating Hotspot"
              createAdHocNetwork
       fi
fi

```
- Make it executable:
    - `sudo chmod +x /usr/bin/autohotspot`

- To test:
    - `sudo reboot`. 
    - After reboot it should manage to connect to your home network.
    - `ssh` into it.
    - Remove your network details from `/etc/wpa_supplocant/wpa_supplicant.conf`
    - `sudo reboot`.
    - You should see a wifi network called "zanzocam-setup" that you can connect to.
    - Connect and `ssh` into the Raspberry again (IP is `10.0.0.5`)


### Prepare setup server
Once the Pi can generate its own network, we make it able to receive HTTP requests by setting up a web server: Nginx.

Instructions (here)[https://www.raspberrypi.org/documentation/remote-access/web-server/nginx.md] for Nginx and (here)[https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uswgi-and-nginx-on-ubuntu-18-04] for Flask.

- Install Nginx: `sudo apt install -y nginx libssl-dev libffi-dev build-essential`
- Start Nginx: `sudo /etc/init.d/nginx start`
- Install venv into `/var/www/setup-server`
    - Create venv: `sudo python3 -m venv /var/www/setup-server/venv`
    - Activate venv: `source /var/www/setup-server/venv/bin/activate`
- Install the requirements for Flask and Ansible: `pip install -r requirements.txt`
- Leave venv: `deactivate`
- Create a systemdunit file: `sudo nano /etc/systemd/system/setup-server.service`
    - Content:
```
[Unit]
Description=uWSGI instance to serve the ZANZOCAM setup server
After=network.target

[Service]
User=zanzocam-bot
Group=www-data
WorkingDirectory=/var/www/setup-server
Environment="PATH=/var/www/setup-server/venv/bin"
ExecStart=/var/www/setup-server/venv/bin/uwsgi --ini setup-server.ini

[Install]
WantedBy=multi-user.target
```
- Enable the service: `sudo systemctl enable setup-server`
- Start the service: `sudo systemctl start setup-server`
- Create Nginx configuration: `sudo nano /etc/nginx/sites-available/setup-server`
    - Content:
```
server {
    listen 80;

    location / {
        include uwsgi_params;
        uwsgi_pass unix:/var/www/setup-server/setup-server.sock;
    }
}
```
- Enable the new config: `sudo ln -s /etc/nginx/sites-available/setup-server /etc/nginx/sites-enabled`
- Disable the default config: `sudo rm /etc/nginx/sites-enabled/default`
    - Check for errors with `sudo nginx -t`
- Restart Nginx: `sudo systemctl restart nginx`
