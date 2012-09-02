class PrivateExc(Exception): pass

class Privacy:
	def __setattr__(self, attr, value):
		if attr in self.privates:
			raise PrivateExc(attr, self)
		else:
			self.__dict__[attr] = value

class Test1(Privacy):
	privates = ['age']

class Test2(Privacy):
	privates = ['name', 'pay']
	def __init__(self):
		#self.__dict__['name'] = 'tom'
		self.name = 'tom'

x = Test1()
y = Test2()

x.name = 'Bob'

y.name = 'Sue'
