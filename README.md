# TechnoBulb

**Updated 20.07.2025**

The bulb's color will change with the output stream of your device (e.g. music), pretty cool right?

# Setup

This app was made for _LEDVANCE RGBW 806lm 9w E27_ and tested with other bulbs, currently the project is set up to handle **2 bulbs**.

```
  $ pip install tinytuya soundcard scapy PySide6 numpy
  $ cd TechnoBulb
  $ cd resync-key
  $ python print_local_keys.py
```

You will need to include your local keys and devices mac adresses in `techno_bulb.py` file
```
  $ cd ..
  $ python techno_bulb.py
```

![image](https://github.com/FLOCK4H/TechnoBulb/assets/161654571/ea1b9f63-d9ac-456d-a641-28c8aaa3e5b3)

The GUI is for simply pausing the algorithm, press 'P' to pause the color at current frame.

# About

This app catches the sound stream of the default output device on the lower level, means it captures the stream before the audio gets to the speakers.
The delay is also minimal, very difficult to notice.
The audio is then converted into magnitude and frequency using FFT (Fast Fourier Transformation) and is applied on the color gradient scheme to finally send the right color via request to the bulb.
