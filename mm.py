import time
import os

import numpy as np
import tifffile
import matplotlib.pyplot as plt
plt.rcParams['image.cmap'] = 'gray'

from mvp import Mvp
mvp = Mvp('COM20')

from pycromanager import Bridge
bridge = Bridge()
mmc = bridge.get_core()
studio = bridge.get_studio()

stage = mmc.get_xy_stage_device()
zdrive = mmc.get_focus_device()

mmc.assign_image_synchro('MU')
#mmc.assign_image_synchro(zdrive)
mmc.assign_image_synchro(stage)

def selectChannel(ch):
    mmc.wait_for_device('MU')
    try:
        mmc.set_config(mmc.get_channel_group(), ch)
    except Exception as e: # really a hack
        time.sleep(5)
        mmc.set_config(mmc.get_channel_group(), ch)
    
def takeImage(display = True):
    mmc.snap_image()
    img = mmc.get_image()
    img = img.reshape(512,512) #the data returned is not the right shape
    if display:
        plt.figure()
        plt.imshow(img)
        plt.show()
    return img

def takeZStack(channelFirst = True, ch = ['DIC', 'FL-480', 'FL-565', 'FL-647'], stepSize = 4, nSteps = 11):
    imagestack = np.zeros((nSteps, len(ch), 512,512), dtype=np.uint16)
    curPos = mmc.get_position()

    if channelFirst:
        for i in range(nSteps):
            z = curPos + (i-nSteps//2) * stepSize
            mmc.set_position(z)
            for k,c in enumerate(ch):
                selectChannel(c)
                imagestack[i, k, ...] = takeImage(display = False)
    else:       
        for k, c in enumerate(ch):
            selectChannel(c)
            for i in range(nSteps):
                z = curPos + (i-nSteps//2) * stepSize
                mmc.set_position(zdrive, z)
                imagestack[i, k, ...] = takeImage(display = False)

    selectChannel('DIC')
    mmc.set_position(curPos)
    return imagestack

def autoFocus(offset = 0):
    #studio.autofocus_now() 
    time.sleep(5) #autofocus has some strange timing problem. wait 5 sec to be safe
    afmng = studio.get_autofocus_manager()
    afmng.get_autofocus_method().full_focus()
    if offset != 0:
        pos = mmc.get_position()
        mmc.set_position(pos + offset)
    time.sleep(3) #needed? for safety

def imageGrid(grid, image_size = 409.6, overlap = 0.12):
    ''' scan a grid.
        grid: a tuple of values, e.g. (5,5)
    '''
    mmc.clear_roi();
    mmc.set_auto_shutter(False)
    mmc.set_shutter_open(True)
    ny,nx = grid
    # curpos = mmc.get_xy_stage_position()
    step_size = image_size * (1.0 - overlap)
    images = []
    for ypos in range(ny):
        for xpos in range(nx):
            images.append(takeImage(False))
            mmc.set_relative_xy_position(-step_size, 0)
        mmc.set_relative_xy_position(step_size * nx, -step_size)
    mmc.set_relative_xy_position(0, step_size * ny)
    mmc.set_shutter_open(False)
    mmc.set_auto_shutter(True)
    return np.stack(images)
  
def long_sleep(min):
    try:
        for _ in range(int(min)):
            for _ in range(10):
                time.sleep(6)
        extra = (min - int(min)) * 60
        time.sleep(extra)
    except KeyboardInterrupt as e:
        stopPump()
        print('Interrupted!!!!!!!!')
        raise e

# List all samples/buffers here as a dictionary
# 'SampleName':(valve1-position, valve2-position, valve3-position)
samples = {'b1':(1,0,2), 'b2':(2,0,2), 's1':(3,0,2), 's2':(4,0,2), 's3':(5,0,2), 's4':(6,0,2), 
           'b3':(0,1,1), 'b4':(0,2,1),'s5':(0,3,1),'s6':(0,4,1),'s7':(0,5,1),'s8':(0,6,1),
          'b5':(0,0,3), 's9':(0,0,4), 's10':(0,0,5), 's11':(0,0,6)}
tube_vols = {'b2':0.326, 's1':0.378, 's2':0.429, 's3':0.335, 's4':0.352, 'b4':0.248, 's5':0.326, 's6':0.326, 's7':0.352, 's8':0.309, 'b5':0.214, 's9':0.240, 's10':0.214, 's11':0.214}

chamber_vol = 0.05
feed_tube_vol = 0.2
total_tube_vol = 0.22
#max peak for valve 3 = 0.225  

def startPump(v = 1.6):
    ''' start the pump. 
    Returns the real flow rate, because the flow rate will be dependent on the voltager.
    '''
    mmc.set_property('AnalogIO', 'Volts', v)
    return v / 1.6 * 0.5 #flow rate is 0.5ml/min if pump vol is 1.6v

def stopPump():
    mmc.set_property('AnalogIO', 'Volts', 0.0)
    
def loadSample(sample_name, volumn, v = 1.6):
    '''
    Load sample into tubing.
    
    sample_name: name of the sample
    volume: the vol of sample to be loaded, in ml
    v: voltage of the pump, deault 1.6
    '''
    v1,v2,v3 = samples[sample_name]
    if v1 > 0:
        mvp.setValvePosition(1, v1)
    if v2 > 0:
        mvp.setValvePosition(2, v2)
    if v3 > 0:
        mvp.setValvePosition(3, v3)
        
    # the valve function returns before the motor is fully settled. wait for 5 sec
    time.sleep(5)
    
    real_flow_rate = startPump(v)
    long_sleep(volumn/real_flow_rate)
    stopPump()

def loadIncubateWash(sample_name, time, buffer_name = 'b5'):
    '''
    Load 4*chamber_vol sample, then push with buffer (default b5) until sample is in chamber.
    Wait for 'time' in minutes. Washing with 10xchamber_vol of buffer (default b1) 
    
    sample_name: name of the sample to be loaded
    time: minutes to be waited after sample is loaded
    buffer_name: the buffer used for washing and for pushing sample to chamber
    '''
    #load
    loadSample(sample_name, chamber_vol * 4)
    loadSample(buffer_name, tube_vols[sample_name])
    long_sleep(time) # 10 min
    #washing
    loadSample(buffer_name, chamber_vol * 10)

def shutDown():
    del mmc
    del studio
    mvp.ser.close()

def imagingStep(pathPrefix = 'test', channels = ['DIC'], grid=(5,5)):
    '''
    Implement an imaging step
    - go through a defined locations in the postion list
    - autofocus
    - scan through a list of color channels
    - for each channel, collect a grid (5x5) of images
    - images are saved in folders \<path\>\\pos<0-N>\\\<channelname\>\\grid\<0-24\>.tif
    '''
    poslist = studio.get_position_list_manager().get_position_list()
    n_pos =  poslist.get_number_of_positions()
    mmc.wait_for_device(stage)
    mmc.wait_for_device('MU')
    
    os.makedirs(pathPrefix, exist_ok=True)
    
    for posNo in range(max(1, n_pos)):
        if n_pos != 0:
            pos = poslist.get_position(posNo)
            mmc.set_xy_position(pos.get_x(), pos.get_y())
            #mmc.set_position(pos.get_z())
        selectChannel('DIC') # make sure changing to DIC. otherwise autofocus will fail.        
        autoFocus()
        for ch in channels:
            selectChannel(ch)
            data = imageGrid(grid)
            pathName = os.path.join(pathPrefix, ch + '.tif')
            tifffile.imwrite(pathName, data, append = True)

    selectChannel('DIC') #change back to DIC to block light
