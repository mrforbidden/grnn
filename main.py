import argparse
import random
import datetime

import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
import numpy as np

from dataset import trafficDataLoader
from model import GRNN


def getTime(begin, end):
    timeDelta = end - begin
    return '%d h %d m %d.%ds' % (timeDelta.seconds // 3600, (timeDelta.seconds%3600) // 60, timeDelta.seconds % 60, timeDelta.microseconds)

timStart = datetime.datetime.now()

parser = argparse.ArgumentParser()
parser.add_argument('--taskID', type=int, default=1, help='traffic prediction task id')
parser.add_argument('--batchSize', type=int, default=1, help='input batch size')
parser.add_argument('--dimHidden', type=int, default=32, help='GRNN hidden state size')
parser.add_argument('--truncate', type=int, default=144, help='BPTT length for GRNN')
parser.add_argument('--nIter', type=int, default=2, help='number of epochs to train')
parser.add_argument('--lr', type=float, default=0.01, help='learning rate')
parser.add_argument('--cuda', action='store_true', help='enables cuda')
parser.add_argument('--verbal', action='store_true', help='print training info or not')
parser.add_argument('--manualSeed', type=int, help='manual seed')

opt = parser.parse_args()
print(opt)

if opt.manualSeed is None:
    opt.manualSeed = random.randint(1, 10000)
print("Random Seed: ", opt.manualSeed)
random.seed(opt.manualSeed)
torch.manual_seed(opt.manualSeed)

if opt.cuda:
    torch.cuda.manual_seed_all(opt.manualSeed)

def main(opt):
    dataLoader = trafficDataLoader(opt.taskID)

    data = np.transpose(dataLoader.data)        # [T, n]
    A = dataLoader.A
    opt.nNode = dataLoader.nNode
    A = A + np.eye(opt.nNode)
    opt.dimFeature = 1

    #--------TEST---------
    #data = data[:, 0]
    #data = data[:, np.newaxis]
    #A = np.array([1.])
    #A = A[:, np.newaxis]
    #opt.nNode = 1
    #------TEST END-------

    data = torch.from_numpy(data[np.newaxis, :, :, np.newaxis]) # [b, T, n, d]
    A = torch.from_numpy(A[np.newaxis, :, :])                   # [b, n, n]

    net = GRNN(opt)
    net.double()
    print(net)

    criterion = nn.MSELoss()

    if opt.cuda:
        net.cuda()
        criterion.cuda()
        data = data.cuda()
        A = A.cuda()

    optimizer = optim.Adam(net.parameters(), lr=opt.lr)

    plt.figure(1, figsize=(12, 5))
    plt.ion

    hState = torch.randn(opt.batchSize, opt.dimHidden, opt.nNode).double()
    yLastPred = 0
    
    for t in range(data.size(1) - opt.truncate):
        x = data[:, t:(t + opt.truncate), :, :]
        y = data[:, (t + 1):(t + opt.truncate + 1), :, :]

        for i in range(opt.nIter):
            process = '[Log] %d propogation, %d epoch. ' % (t + 1, i + 1)
            timStamp = datetime.datetime.now()
            prediction, hNew = net(x, hState, A)
            print(process + 'Forward used: %s.' % getTime(timStamp, datetime.datetime.now()))
            hState = hState.data

            loss = criterion(prediction, y)
            optimizer.zero_grad()
            timStamp = datetime.datetime.now()
            loss.backward()
            print(process + 'Backward used: %s.' % getTime(timStamp, datetime.datetime.now()))
            optimizer.step()
        
        _, hState = net.propogator(x[:, 0, :, :], hState, A)
        hState = hState.data

        if t == 0:
            plt.plot([v for v in range(opt.truncate)], x[:, :, 0, :].data.numpy().flatten(), 'r-')
            plt.plot([v + 1 for v in range(opt.truncate)], prediction[:, :, 0, :].data.numpy().flatten(), 'b-')
        else:
            plt.plot([t + opt.truncate - 2, t + opt.truncate - 1], x[:, -2:, 0, :].data.numpy().flatten(), 'r-')
            plt.plot([t + opt.truncate - 1, t + opt.truncate], [yLastPred, prediction[0, -1, 0, 0]], 'b-')
        plt.draw()
        plt.pause(0.5)
        yLastPred = prediction[0, -1, 0, 0]

    plt.ioff()
    plt.show()


if __name__ == "__main__":
    main(opt)

