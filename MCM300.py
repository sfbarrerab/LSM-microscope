import time
import serial

class Controller:
    '''
    Basic device adaptor for thorlabs MCM3000 and MCM3001 3-axis controllers.
    Not implemented:
    - stop function (not useful?)
    - query motor status (not working? documentation error?)
    Test code runs and seems robust.
    '''
    def __init__(self,
                 which_port,
                 name='MCM3000',
                 stages=3*(None,), # connected e.g. (None, None, 'ZFM2030')
                 reverse=3*(False,), # reverse e.g. (False, False, True)
                 verbose=True,
                 very_verbose=False):
        self.name = name
        self.stages = stages
        self.reverse = reverse        
        self.verbose = verbose
        self.very_verbose = very_verbose
        if self.verbose: print("%s: opening..."%self.name, end='')
        try:
            self.port = serial.Serial(
                port=which_port, baudrate=9600, timeout=5)
        except serial.serialutil.SerialException:
            raise IOError(
                '%s: no connection on port %s'%(self.name, which_port))
        if self.verbose: print(" done.")
        assert type(self.stages) == tuple and type(self.reverse) == tuple
        assert len(self.stages) == 3 and len(self.reverse) == 3
        for element in self.reverse: assert type(element) == bool
        self._encoder_counts= 3*[None]
        self._encoder_counts_tol= 3*[1] # can hang if < 1 count
        self._target_encoder_counts= 3*[None]
        self._um_per_count = 3*[None]
        self._position_limit_um = 3*[None]
        self.position_um = 3*[None]
        supported_stages = { # 'Type': (_um_per_count, +- _position_limit_um, )
                        'ZFM2020':( 0.2116667, 1e3 * 12.7),
                        'ZFM2030':( 0.2116667, 1e3 * 12.7),
                        'MMP-2XY':(0.5, 1e3 * 25.4)}
        self.channels = []
        for channel, stage in enumerate(self.stages):
            if stage is not None:
                assert stage in supported_stages, (
                    '%s: stage \'%s\' not supported'%(self.name, stage))
                self.channels.append(channel)
                self._um_per_count[channel] = supported_stages[stage][0]
                self._position_limit_um[channel] = supported_stages[stage][1]
                self._get_encoder_counts(channel)
        self.channels = tuple(self.channels)
        if self.verbose:
            print("%s: stages:"%self.name, self.stages)
            print("%s: reverse:"%self.name, self.reverse)
            print("%s: um_per_count:"%self.name, self._um_per_count)
            print("%s: position_limit_um:"%self.name, self._position_limit_um)
            print("%s: position_um:"%self.name, self.position_um)

    def _send(self, cmd, channel, response_bytes=None):
        assert channel in self.channels, (
            '%s: channel \'%s\' is not available'%(self.name, channel))
        if self.very_verbose:
            print('%s(ch%s): sending cmd: %s'%(self.name, channel, cmd))
        self.port.write(cmd)
        if response_bytes is not None:
            response = self.port.read(response_bytes)
        else:
            response = None
        assert self.port.inWaiting() == 0
        if self.very_verbose:
            print('%s(ch%s): -> response: %s'%(self.name, channel, response))
        return response

    def _encoder_counts_to_um(self, channel, encoder_counts):
        um = encoder_counts * self._um_per_count[channel]
        if self.reverse[channel]: um = - um + 0 # +0 avoids -0.0
        if self.very_verbose:
            print('%s(ch%s): -> encoder counts %i = %0.2fum'%(
                self.name, channel, encoder_counts, um))
        return um

    def _um_to_encoder_counts(self, channel, um):
        encoder_counts = int(round(um / self._um_per_count[channel]))
        if self.reverse[channel]:
            encoder_counts = - encoder_counts + 0 # +0 avoids -0.0
        if self.very_verbose:
            print('%s(ch%s): -> %0.2fum = encoder counts %i'%(
                self.name, channel, um, encoder_counts))
        return encoder_counts

    def _get_encoder_counts(self, channel):
        if self.very_verbose:
            print('%s(ch%s): getting encoder counts'%(self.name, channel))
        channel_byte = channel.to_bytes(1, byteorder='little')
        cmd = b'\x0a\x04' + channel_byte + b'\x00\x00\x00'
        response = self._send(cmd, channel, response_bytes=12)
        assert response[6:7] == channel_byte # channel = selected
        self._encoder_counts[channel] = int.from_bytes(
            response[-4:], byteorder='little', signed=True)
        if self.very_verbose:
            print('%s(ch%s): -> encoder counts = %i'%(
                self.name, channel, self._encoder_counts[channel]))
        self.position_um[channel] = self._encoder_counts_to_um(
            channel, self._encoder_counts[channel])
        return self._encoder_counts[channel]

    def _set_encoder_counts_to_zero(self, channel):
        # WARNING: this device adaptor assumes the stage encoder will be set to
        # zero at the centre of it's range for +- stage_position_limit_um checks
        if self.verbose:
            print('%s(ch%s): setting encoder counts to zero'%(
                self.name, channel))
        channel_byte = channel.to_bytes(2, byteorder='little')
        encoder_bytes = (0).to_bytes(4, 'little', signed=True) # set to zero
        cmd = b'\x09\x04\x06\x00\x00\x00' + channel_byte + encoder_bytes
        self._send(cmd, channel)
        while True:
            self._get_encoder_counts(channel)
            if self._encoder_counts[channel] == 0:
                break
        if self.verbose:
            print('%s(ch%s): -> done'%(self.name, channel))
        return None

    def _move_to_encoder_count(self, channel, encoder_counts, block=True):
        if self._target_encoder_counts[channel] is not None:
            self._finish_move(channel)
        if self.very_verbose:
            print('%s(ch%s): moving to encoder counts = %i'%(
                self.name, channel, encoder_counts))
        self._target_encoder_counts[channel] = encoder_counts
        encoder_bytes = encoder_counts.to_bytes(4, 'little', signed=True)
        channel_bytes = channel.to_bytes(2, byteorder='little')
        cmd = b'\x53\x04\x06\x00\x00\x00' + channel_bytes + encoder_bytes
        self._send(cmd, channel)
        if block:
            self._finish_move(channel)
        return None

    def _finish_move(self, channel, polling_wait_s=0.1):
        if self._target_encoder_counts[channel] is None:
            return
        while True:
            encoder_counts = self._get_encoder_counts(channel)
            if self.verbose: print('.', end='')
            time.sleep(polling_wait_s)
            target = self._target_encoder_counts[channel]
            tolerance = self._encoder_counts_tol[channel]
            if target - tolerance <= encoder_counts <= target + tolerance:
                break
        if self.verbose:
            print('\n%s(ch%s): -> finished move.'%(self.name, channel))
        self._target_encoder_counts[channel] = None
        return None

    def _legalize_move_um(self, channel, move_um, relative):
        if self.verbose:
            print('%s(ch%s): requested move_um = %0.2f (relative=%s)'%(
                self.name, channel, move_um, relative))
        if relative:
            # update position in case external device was used (e.g. joystick)
            self._get_encoder_counts(channel)
            move_um += self.position_um[channel]
        limit_um = self._position_limit_um[channel]
        assert - limit_um <= move_um <= limit_um, (
            '%s: ch%s -> move_um (%0.2f) exceeds position_limit_um (%0.2f)'%(
                self.name, channel, move_um, limit_um))
        move_counts = self._um_to_encoder_counts(channel, move_um)
        legal_move_um = self._encoder_counts_to_um(channel, move_counts)
        if self.verbose:
            print('%s(ch%s): -> legal move_um = %0.2f '%(
                self.name, channel, legal_move_um) +
                  '(%0.2f requested)'%move_um)
        return legal_move_um

    def get_position_um(self, channel):
        if self.verbose:
            print('%s(ch%s): getting position'%(self.name, channel))
        self._get_encoder_counts(channel)
        if self.verbose:
            print('%s(ch%s): -> position_um = %0.2f'%(
                self.name, channel, self.position_um[channel]))
        return self.position_um[channel]

    def move_um(self, channel, move_um, relative=True, block=True):
        legal_move_um = self._legalize_move_um(channel, move_um, relative)
        if self.verbose:
            print('%s(ch%s): moving to position_um = %0.2f'%(
                self.name, channel, legal_move_um))
        encoder_counts = self._um_to_encoder_counts(channel, legal_move_um)
        self._move_to_encoder_count(channel, encoder_counts, block)
        return legal_move_um

    def close(self):
        if self.verbose: print("%s: closing..."%self.name, end=' ')
        self.port.close()
        if self.verbose: print("done.")
        return None

if __name__ == '__main__':
    channel = 0
    controller = Controller(which_port='COM4',
                            stages=('ZFM2020', 'ZFM2020', 'ZFM2020'),
                            reverse=(False, False, False),
                            verbose=True,
                            very_verbose=False)

    # re-set zero:
    controller.move_um(channel, 1000)
    controller._set_encoder_counts_to_zero(channel)
    controller.move_um(channel, 0)

    print('\n# Check position attribute:')
    print('-> position_um = %0.2f'%controller.position_um[channel])

    print('\n# Get updated position:')
    controller.get_position_um(channel)

    print('\n# Home:')
    controller.move_um(channel, 0, relative=False)

    print('\n# Some relative moves:')
    for moves in range(3):
        controller.move_um(channel, 1000)
    for moves in range(3):
        controller.move_um(channel, -1000)

    print('\n# Legalized move:')
    legal_move_um = controller._legalize_move_um(channel, 1000, relative=True)
    controller.move_um(channel, legal_move_um)

    print('\n# Some random absolute moves:')
    from random import randrange
    for moves in range(3):
        random_move_um = randrange(-1000, 1000)
        move = controller.move_um(channel, random_move_um, relative=False)

    print('\n# Non-blocking move:')
    controller.move_um(channel, 2000, block=False)
    controller.move_um(channel, 1000, block=False)
    print('(immediate follow up call forces finish on pending move)')
    print('doing something else')
    controller._finish_move(channel)

    print('\n# Encoder tolerance check:')
    # hangs indefinetly if self._encoder_counts_tol[channel] < 1 count
    for i in range(3):
        controller.move_um(channel, 0, relative=False)
        controller.move_um(channel, 0.2116667, relative=False)

    controller.close()