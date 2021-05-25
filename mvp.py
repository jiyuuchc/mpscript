import serial

class Mvp:
	stx, etx, eot, enq, ack, nak = (b'\x02',b'\x03',b'\x04',b'\x05',b'\x06',b'\x15')

	def __init__(self, port):
		self.ser = serial.Serial(port, bytesize=7, parity=serial.PARITY_EVEN, stopbits=2, timeout=1.0)

	def getBcc(self, s):
		bcc = 0
		for b in s:
			bcc = bcc ^ b
		bcc = bcc ^ 3
		bcc = bcc ^ 255
		return bytes([bcc])

	def sendCmd(self, s):
		self.ser.write(self.stx)
		self.ser.write(s)
		self.ser.write(self.etx)
		self.ser.write(self.getBcc(s))

		return self.ser.read()

	def selectDev(self, n):
		self.ser.write(b'0%i'%n)
		self.ser.write(self.enq)

		return self.ser.read()

	def readResp(self):
		ans = self.ser.read()
		if (ans != self.stx) :
			return None
		s = b''
		ans = b''
		while (ans != self.etx):
			s += ans
			ans = self.ser.read()
		ans = serlf.ser.read()
		if getBcc(s) != ans:
			return None
		else:
			return s

	def setValvePosition(self, dev, pos):
		self.ser.write(self.eot)
		self.selectDev(dev)
		self.sendCmd(b'Vn%i'%pos)
		self.sendCmd(b'Ur')
		self.sendCmd(self.eot)
