# TinyML: Cloud Classfier - By: Swapnil - Tue Aug 3 2021

import pyb, machine, sensor, os, tf, gc, time
import network, socket, ustruct, utime, random
import urequests, json, hashlib, image

om2m = "http://20.214.226.173:8080"
headers = {
    "Content-Type": "application/vnd.onem2m-res+json; ty=28",
    "Accept": "application/json",
    "X-M2M-RI": "unknownRI",
    "X-M2M-Origin": "admin:admin"
}

def Connect_WiFi():
    SSID='SK_WiFi0666' # Network SSID
    KEY='1507033098'  # Network key

    # Init wlan module and connect to network
    print("Trying to connect with Wi-Fi... (This may take a while)...")
    wlan = network.WLAN(network.STA_IF)
    wlan.deinit()
    wlan.active(True)
    wlan.connect(SSID, KEY, timeout=30000)
    # We should have a valid IP now via DHCP
    print("WiFi Connected ", wlan.ifconfig())

    return wlan

def Ntp_Time():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = socket.getaddrinfo("pool.ntp.org", 123)[0][4]
    # Send query
    client.sendto('\x1b' + 47 * '\0', addr) # Get addr info via DNS
    data, address = client.recvfrom(1024)

    # Print time
    TIMESTAMP = 2208988800+946684800
    t = ustruct.unpack(">IIIIIIIIIIII", data)[10] - TIMESTAMP
    print ("Year:%d Month:%d Day:%d Time: %d:%d:%d" % (utime.localtime(t)[0:6]))

    client.close() # close socket

    return t

def File_Name(rtc):
    # Extract the date and time from the RTC object.
    dateTime = rtc.datetime()
    year = str(dateTime[0])
    month = '%02d' % dateTime[1]
    day = '%02d' % dateTime[2]
    hour = '%02d' % dateTime[4]
    minute = '%02d' % dateTime[5]
    second = '%02d' % dateTime[6]
    subSecond = str(dateTime[7])

    newName='I'+year+month+day+hour+minute+second+'_'
    return newName

def Make_FlexContainer():
    print("Making FlexContainer...")
    body = {
        "hd:binOt" : {
            "rn": "BinaryObject",
            "fcied": True,
            "mni": 10
        }
    }
    result = urequests.post(om2m + "/~/in-cse/in-name/SDT_IPE", headers=headers, json=body)
    print("FlexContainer CREATE")
    return result

def Retrieve_FlexContainer():
    print("Retrieve FlexContainer...")
    rheader = {
        "Accept": "application/json",
        "X-M2M-RI": "unknownRI",
        "X-M2M-Origin": "admin:admin"
    }
    result = urequests.get(om2m + "/~/in-cse/in-name/SDT_IPE/BinaryObject", headers=rheader)
    print("RETRIEVE status code:", result.status_code)
    if result.status_code == 404:
        return False
    elif result.status_code == 200:
        return True


def Send_Prediction(prediction, image_name, image_content, battery_level):
    print("Sending Prediction...")
    size = len(image_content)
    sha = int.from_bytes(hashlib.sha1(image_content).digest(), 'big')
    objet = int.from_bytes(bytes(image_content), 'big')
    print("size:", size)
    print("hash:", sha)
    print("objet:", objet)
    body = {
        "hd:binOt" : {
            "fcied": True,
            "mni": 10,
            "size": size,
            "hash": sha,
            "objet": objet,
            "objTe": "byte",
            "batLe": battery_level,
            "imgNa": image_name,
            "predic": prediction
        }
    }
    print("OM2M PUTTING")
    result = urequests.put(om2m + "/~/in-cse/in-name/SDT_IPE/BinaryObject", headers=headers, json=body)
    print("OM2M UPDATED")
    return result

def Inference(img):
    # Load tf network and labels
    net = "trained.tflite"
    labels = [line.rstrip('\n') for line in open("labels.txt")]
    predicted_label = ''

    # default settings just do one detection... change them to search the image...
    for obj in tf.classify(net, img, min_scale=1.0, scale_mul=0.8, x_overlap=0.5, y_overlap=0.5):
        # This combines the labels and confidence values into a list of tuples
        predictions_list = list(zip(labels, obj.output()))
        # Abstract max value and its index from the output
        predictions_max = max(obj.output())
        predictions_max_index = obj.output().index(predictions_max)
        predicted_label = labels[predictions_max_index]
        print("Prediction = %s" % predicted_label)

        for i in range(len(predictions_list)):
            print("%s = %f" % (predictions_list[i][0], predictions_list[i][1]))
    return predicted_label, predictions_list, labels

def Battery_Level():
    return random.randint(0, 100)

def main():
    BLUE_LED_PIN = 3
    GREEN_LED_PIN = 2
    RED_LED_PIN = 1

    demo = False
    newFile = False

    pyb.LED(BLUE_LED_PIN).on()
    rtc = pyb.RTC()
    wlan = Connect_WiFi()
    pyb.LED(BLUE_LED_PIN).off()

    pyb.LED(GREEN_LED_PIN).on()
    t = Ntp_Time()
    # datetime format: year, month, day, weekday (Monday=1, Sunday=7),
    # hours (24 hour clock), minutes, seconds, subseconds (counds down from 255 to 0)
    rtc.datetime((utime.localtime(t)[0], utime.localtime(t)[1], utime.localtime(t)[2],
                utime.localtime(t)[6], utime.localtime(t)[3], utime.localtime(t)[4],
                utime.localtime(t)[5], 0))
    try:
        os.stat('dataset.csv')
    except OSError: # If the log file doesn't exist then set newFile to True
        newFile = True

    # Enable RTC interrupts every sleep_duration, camera will RESET after wakeup from deepsleep Mode.
    sleep_duration = 1	# This duration should be in MINUTES(default : 60).
    rtc.wakeup(sleep_duration*60*1000)

    sensor.reset() # Initialize the camera sensor.
    sensor.set_pixformat(sensor.GRAYSCALE)
    sensor.set_framesize(sensor.QQQVGA)
    sensor.skip_frames(time = 2000) # Let new settings take affect.

    if not Retrieve_FlexContainer():
        Make_FlexContainer()

    print("Setting Ready")
    pyb.LED(GREEN_LED_PIN).off()

    while(True):
        pyb.LED(BLUE_LED_PIN).on()

        img = sensor.snapshot()
        predicted_label, predictions_list, labels = Inference(img)

        print("Save Image")
        newName = File_Name(rtc) + predicted_label
        if not "images" in os.listdir(): os.mkdir("images")
        img.save('images/' + newName, quality=100)

        print("Save LOG")
        if(newFile):
            with open('dataset.csv', 'a') as datasetFile:
                datasetFile.write('Image_File_Name, ')
                for i in range(len(labels)):
                    datasetFile.write(labels[i] + ', ')
                datasetFile.write('Prediction' + '\n')
                datasetFile.write(newName + ', ')
                for i in range(len(predictions_list)):
                    datasetFile.write(str(predictions_list[i][1]) + ', ')
                datasetFile.write(predicted_label + '\n')
        else:
            with open('dataset.csv', 'a') as datasetFile:
                datasetFile.write(newName + ', ')
                for i in range(len(predictions_list)):
                    datasetFile.write(str(predictions_list[i][1]) + ', ')
                datasetFile.write(predicted_label + '\n')

        # Send prediction and image to a remote server
        Send_Prediction(predicted_label, str(newName), img.bytearray(), str(Battery_Level()))

        gc.collect()

        print("Flow End...")
        time.sleep_ms(5*1000)
        pyb.LED(BLUE_LED_PIN).off()

        if not demo:
            break

    wlan.disconnect()
    machine.deepsleep()

main()
