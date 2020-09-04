import random
import math
from event import Event
from priority_queue import PriorityQueue


# global variables

MAXBUFFER = float('inf')                          
gel = PriorityQueue()                             # global events list
hosts = []
time = 0                                          # current time
DIFS = 0.0001                                     # in sec
SIFS = 0.00005
ackReceived = False                               # flag for if ACK is received by sender
sensingTime = 0.00001
k = 0                                             # number of collisions
numBytes = 0
totalDelay = 0                                    # (time arrived in queue - time arrived in receiver) for all hosts (use transmission cap of 10mpbs)

class Host:
    def __init__(self):
        self.buffer = []           # store packets
        self.length = 0            # buffer length
        self.channelBusy = 0       # channel will be counted as busy at the time the packet arrives 

    def packetReady(self, dataSize, time, transmissionTime, event,
                            sendIndex, receiveIndex, channelBusyGlobal):
        global waitType
        global totalDelay
        time = event.time
        self.buffer.append(time)
        self.channelBusy = 1
        # assume you start waiting 0.01msec due to sensing after host is ready to send data
        totalDelay += 0.00001
        waitEvent = Event(time + 0.00001, "wait_frame")
        channelBusyGlobal = 1
        gel.insert(waitEvent)

    def waitDIFS(self, dataSize, time, transmissionTime, event,
                   sendIndex, receiveIndex, channelBusyGlobal):
        global DIFS
        global k
        global totalDelay
        time = event.time
        if channelBusyGlobal == 0:
            counter = DIFS
        else: 
            counter = DIFS + randomBackoff(k)
        totalDelay += counter
        transmitEventTime = time + counter
        while(counter > 0 ):
            if channelBusyGlobal == 0:
                counter = counter-1
        transmitEvent = Event(transmitEventTime, "transmit_frame")
        gel.insert(transmitEvent)
    
    def transmitFrame(self, dataSize, time, transmissionTime, event,
                        sendIndex, receiveIndex, channelBusyGlobal):
        global numBytes
        channelBusyGlobal = 0
        numBytes += dataSize
        time = event.time
        collisionCheckEventTime = time + transmissionTime
        collisionCheckEvent = Event(collisionCheckEventTime, "collision_check")
        gel.insert(collisionCheckEvent)
        waitEventTime = time + transmissionTime
        waitEvent = Event(waitEventTime, "wait_timeout")
        gel.insert(waitEvent)

    def waitACKTimeout(self, dataSize, time, transmissionTime, event,
                       sendIndex, receiveIndex, channelBusyGlobal):
        global totalDelay
        time = event.time
        counter = 1.5 * (SIFS + ((64 * 8)/(11 * math.pow(10,6)))/1000)
        while(counter >= 0 ):  # start timer for ACK
            if ackReceived:
                hosts[sendIndex].buffer.pop(0) # remove transmitted packet from sender buffer
                totalDelay += 1.5 * (SIFS + ((64 * 8)/(10 * math.pow(10,6)))/1000)
                self.channelBusy = 0
                # process any remaining packets in queue
                if gel.isEmpty() == False:
                    gel.delete() # delete ack transmission event
                processRest = Event(1.5 * (((SIFS + ((64 * 8)/(11 * math.pow(10,6)))/1000)) - counter) + time,"ready")
                gel.insert(processRest) 
            counter = counter-1
        if counter == -1: # timeout, assume collision
            totalDelay += 1.5 * (SIFS + ((64 * 8)/(10 * math.pow(10,6)))/1000)
            timeoutEvent = Event(time + 1.5 * (SIFS + ((64 * 8)/(11 * math.pow(10,6)))/1000), "timeout")
            gel.insert(timeoutEvent)

    # checks for collisions, collision exists if two hosts have same packet arrival time (means they
    # start transmitting at the same time)
    def checkCollision(self, sendIndex, receiveIndex, sender, N, event):
        global k
        global hosts
        global time
        time = event.time
        collision = False
        for i in range(1, sendIndex) + range(sendIndex+1, N):
            if len(hosts[i].buffer) > 0:
                if sender.buffer[0] == hosts[i].buffer[0]:
                    k = k + 1
                    collision = True # collision is true, do not add packet to receiver queue)
        if collision == False:
            hosts[receiveIndex].buffer.append(hosts[sendIndex].buffer[0])
            queueACKEvent = Event(time, "queue_ack")
            gel.insert(queueACKEvent)

    def queueACK(self, dataSize, time, transmissionTime, event,
                        sendIndex, receiveIndex, channelBusyGlobal):
        global totalDelay
        channelBusyGlobal = 1
        time = event.time
        lastPacket = self.buffer[len(self.buffer) - 1] # since no collision, create ACK packet and add to front of queue
        self.buffer.append(lastPacket)
        for i in range(len(self.buffer) - 2, 0):
            self.buffer[i + 1] = self.buffer[i]
        self.buffer[0] = time
        waitEvent = Event(time + 0.00001, "wait_ack")
        totalDelay += 0.00001
        gel.insert(waitEvent)

    def waitSIFS(self, dataSize, time, transmissionTime, event,
                   sendIndex, receiveIndex, channelBusyGlobal):
        global SIFS
        global k
        global totalDelay
        time = event.time
        if channelBusyGlobal == 0:
            counter = SIFS
        else: 
            counter = SIFS + randomBackoff(k)
        totalDelay += counter
        transmitEventTime = time + counter
        while(counter > 0 ):
            if channelBusyGlobal == 0:
                counter = counter-1
        # send ACK when counter reaches 0
        transmitEvent = Event(transmitEventTime, "transmit_ack")
        gel.insert(transmitEvent)

    def transmitAck(self, dataSize, time, transmissionTime, event,
                        sendIndex, receiveIndex, channelBusyGlobal):
        global ackReceived
        global numBytes
        time = event.time
        ackReceived = True
        numBytes += 64
        self.buffer.pop(0) # remove the ack from receiver queue
        channelBusyGlobal = 0
        if gel.isEmpty() == False:
            gel.delete() # delete waitACKTimeout event
        

# pass in lambda as rate
def negExpDist(rate):
    random_gen = random.random()
    return ((-1/float(rate))*math.log(1-random_gen)) % 1544
  
# pass in number of collisions (k)
def randomBackoff(k):
    bkoff = random.choice(range(1,100))
    exp = random.choice(range(1,int(math.pow(2,k+1)))) 
    return bkoff * exp

def main():
    N = input("Number of wireless hosts:  ")
    arrivalRate = input("Arrival rate: ")
    # create N hosts
    for i in range(N):
        host = Host()
        hosts.append(host)

    # schedule transmission event & add to gel
    eventTime = negExpDist(arrivalRate)          #first arrival time
    firstTransmission = Event(eventTime,"ready")
    gel.insert(firstTransmission)
    channelBusyGlobal = 0

    for i in range(100000):
        if gel.isEmpty() == False:
            event = gel.delete()
            if event.event_category == "ready":
                dataSize = negExpDist(arrivalRate)
                transmissionTime = ((dataSize * 8)/(11 * math.pow(10,6)))/1000
                sendIndex = random.choice(range(1, N))       # randomly select one sender host and one receiver host
                receiveIndex = random.choice(range(1, sendIndex) + range(sendIndex+1, N))
                sender = hosts[sendIndex]
                receiver = hosts[receiveIndex]
                #nextEventTime = time + negExpDist(arrivalRate)     # schedule next transmission event & add to gel
                #nextTransmission = Event(nextEventTime, "ready")
                #gel.insert(nextTransmission)
                sender.buffer.append(time)
                sender.packetReady(dataSize, time, transmissionTime, event,
                                   sendIndex, receiveIndex, channelBusyGlobal)
                #print("ready event")
            elif event.event_category == "wait_frame":
                sender.waitDIFS(dataSize, time, transmissionTime, event,
                            sendIndex, receiveIndex, channelBusyGlobal)
                #print("waiting before transmitting (DIFS)")
            elif event.event_category == "wait_ack":
                receiver.waitSIFS(dataSize, time, transmissionTime, event,
                            sendIndex, receiveIndex, channelBusyGlobal)
                #print("waiting before sending ACK (SIFS)")
            elif event.event_category == "wait_timeout":
                sender.waitACKTimeout(dataSize, time, transmissionTime, event,
                            sendIndex, receiveIndex, channelBusyGlobal)
                #print("ACK countdown timer")
            elif event.event_category == "transmit_frame":
                sender.transmitFrame(dataSize, time, transmissionTime, event,
                                    sendIndex, receiveIndex, channelBusyGlobal)
                #print("transmission of frame complete")
            elif event.event_category == "transmit_ack":
                receiver.transmitAck(dataSize, time, transmissionTime, event,
                                    sendIndex, receiveIndex, channelBusyGlobal)
                #print("transmission of ack complete")
            elif event.event_category == "collision_check":
                receiver.checkCollision(sendIndex, receiveIndex, sender, N, event)
                #print("checked for collision")
            elif event.event_category == "queue_ack":
                receiver.queueACK(dataSize, time, transmissionTime, event,
                                sendIndex, receiveIndex, channelBusyGlobal)
                #print("queued ACK")
            elif event.event_category == "timeout":
                sender.waitDIFS(dataSize, time, transmissionTime, event,
                                 sendIndex, receiveIndex, channelBusyGlobal)
                #print("timeout, retransmit")
        if gel.isEmpty():
            print("The throughput is: ")
            print(numBytes/time) 
            print("Average network delay is: ")
            print(totalDelay*1000/(numBytes/time))
            exit()
main()
