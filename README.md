# halviewer

graphical halviewer for linuxcnc

reads the hal from running linuxcnc session and shows the signals in realtime

![screenshot](./halviewer.png)

## quickstart
install depends
```
apt-get install python3-pyqt5 python3-graphviz
```

before running halviewer, you need to run linuxcnc, than:
```
python3 halviewer.py
```

if you want to use pyqt6 support:
```
python3 halviewer.py -6
```


[![HalViewer](https://img.youtube.com/vi/Ma7J_gvicco/0.jpg)](https://www.youtube.com/watch?v=Ma7J_gvicco&feature=youtu.be "HalViewer")
