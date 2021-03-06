import copy
import subprocess

import tornado.ioloop
import toro

import grotlogic.game


class Game(object):

    TIMEOUT = 10

    class Player(grotlogic.game.Game):

        def __init__(self, user, board):
            super(Game.Player, self).__init__(board)

            self.user = user
            self.ready = toro.Event()
            self.moved = None

        def start_move(self, x, y):
            try:
                super(Game.Player, self).start_move(x, y)
            finally:
                self.moved = (x, y)
                self.ready.set()

        def skip_move(self):
            try:
                super(Game.Player, self).skip_move()
            finally:
                self.moved = None
                self.ready.set()

        def get_state(self, board=True):
            state = super(Game.Player, self).get_state(board)
            state.update({
                'moved': self.moved
            })

            return state

    def __init__(self, board):
        self.board = board
        self.round = 0

        self.on_change = toro.Condition()
        self.on_end = toro.Condition()
        self.on_progress = toro.Condition()

        self._players = {}
        self._future_round = None

    def __getitem__(self, user):
        user = user if isinstance(user, str) else str(user.id)

        return self._players[user]

    @property
    def started(self):
        return self.round != 0

    @property
    def ended(self):
        return self.started and self._future_round is None

    @property
    def players(self):
        players = self._players.values()
        players = sorted(
            players,
            key=lambda player: player.user
        )
        players = sorted(
            players,
            key=lambda player: (player.score, player.moves),
            reverse=True,
        )

        return players

    @property
    def players_active(self):
        return (
            player
            for player in self._players.values()
            if player.is_active()
        )

    @property
    def players_unready(self):
        return (
            player
            for player in self.players_active
            if not player.ready.is_set()
        )

    def add_player(self, user):
        player = self.Player(user, copy.copy(self.board))
        self._players[str(user.id)] = player

        self.on_change.notify_all()

        return player

    def start(self):
        self._new_round()

    def _new_round(self):
        self.round += 1

        for player in self.players_active:
            player.ready.clear()

            tornado.ioloop.IOLoop.instance().add_future(
                player.ready.wait(), self._player_ready
            )

        self._future_round = tornado.ioloop.IOLoop.instance().call_later(
            self.TIMEOUT, self._end_round
        )

        self.on_progress.notify_all()

    def _end_round(self):
        for player in self.players_unready:
            player.skip_move()

    def _player_ready(self, future):
        self.on_change.notify_all()

        if any(self.players_unready):
            return

        if self._future_round:
            tornado.ioloop.IOLoop.instance().remove_timeout(self._future_round)

            self._future_round = None

        if any(self.players_active):
            self._new_round()
        else:
            self.on_end.notify_all()


class GameContest(Game):

    class PlayerNotQualifiedException(Exception):
        pass

    QUALIFICATION_TEST = lambda user: True

    def add_player(self, user):
        if not GameContest.QUALIFICATION_TEST(user):
            raise GameContest.PlayerNotQualifiedException()

        return super(GameContest, self).add_player(user)


class GameDev(Game):

    class Player(Game.Player):
        def start_move(self, x, y):
            try:
                self.moves = 1
                self.score = 0

                super(GameDev.Player, self).start_move(x, y)
            finally:
                self.ready.clear()

        def skip_move(self):
            pass

        def is_active(self):
            return True

    @property
    def started(self):
        return True

    @property
    def ended(self):
        return False

    @property
    def players(self):
        return []

    def __getitem__(self, user):
        try:
            return super(GameDev, self).__getitem__(user)
        except LookupError:
            return self.add_player(user)

    def start(self):
        pass


class GameDuel(Game):

    def add_player(self, user):
        player = super(GameDuel, self).add_player(user)

        if len(self.players) == 2:
            self.start()
        else:
            #TODO bot
            subprocess.Popen(
                ['python3', '../grot-stxnext-bot/bot.py', 'STXNext', '1']
            )

        return player
