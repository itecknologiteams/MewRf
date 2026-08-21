from com.rfid.helper.Helper_Protocol import Helper_Protocol


class RingBufferManager:

    def __init__(self,bufferSize):
        # 存放内存的数组
        self.Buffer = [0] * bufferSize
        # 写入数据大小
        self.DataCount = 0
        # 数据起始索引
        self.DataStart = 0
        # 数据结束索引
        self.DataEnd = 0

    # 从缓存下标位置
    def Index(self,index):
        if index > self.DataCount:
            raise Exception("环形缓冲区异常，索引溢出")
        if self.DataStart + index < len(self.Buffer):
            return self.Buffer[self.DataStart + index]
        else:
            return self.Buffer[(self.DataStart + index) - len(self.Buffer)]

    # 清空全部数据
    def ClearAll(self):
        self.DataCount = 0

    def Clear(self,count):
        # 如果需要清理的数据大于现有数据大小，则全部清理
        if count >= self.DataCount:
            self.DataCount = 0
            self.DataStart = 0
            self.DataEnd = 0
        else:
            if self.DataStart + count >= len(self.Buffer):
                self.DataStart = (self.DataStart + count) - len(self.Buffer)
            else:
                self.DataStart += count
            self.DataCount -= count
    # 写入缓存数据 简单用法 WriteBuffer(buffer, 0, buffer.length);
    def WriteBuffer(self,buffer,offset,count):
        reserveCount = len(self.Buffer) - self.DataCount
        # 可用空间够使用
        if reserveCount > count:
            # 数据没到结尾
            if self.DataEnd + count < len(self.Buffer):
                Helper_Protocol.arrayCopy(buffer, offset, self.Buffer, self.DataEnd, count)
                self.DataEnd += count
                self.DataCount += count
            else:
                # 数据结束索引超出结尾 循环到开始
                overflowIndexLength = (self.DataEnd + count) - len(self.Buffer)
                endPushIndexLength = count - overflowIndexLength
                Helper_Protocol.arrayCopy(buffer, offset, self.Buffer, self.DataEnd, endPushIndexLength)
                self.DataEnd = 0
                offset += endPushIndexLength
                self.DataCount += endPushIndexLength
                if overflowIndexLength != 0:
                    Helper_Protocol.arrayCopy(buffer, offset, self.Buffer, self.DataEnd, overflowIndexLength)
                    self.DataEnd += overflowIndexLength # 结束索引
                    self.DataCount += overflowIndexLength # 缓存大小
    # 读取缓存数据
    def ReadBuffer(self,targetBytes,offset,count):
        if count > self.DataCount:
            raise Exception('环形缓冲区异常，读取长度大于数据长度')
        if self.DataStart + count < len(self.Buffer):
            Helper_Protocol.arrayCopy(self.Buffer, self.DataStart, targetBytes, offset, count)
        else:
            overflowIndexLength = (self.DataStart + count) - len(self.Buffer) # 超出索引长度
            endPushIndexLength = count - overflowIndexLength # 填充在末尾的数据长度
            Helper_Protocol.arrayCopy(self.Buffer,self.DataStart, targetBytes, offset, endPushIndexLength)
            offset += endPushIndexLength
            if overflowIndexLength != 0:
                Helper_Protocol.arrayCopy(self.Buffer, 0, targetBytes, offset, overflowIndexLength)












