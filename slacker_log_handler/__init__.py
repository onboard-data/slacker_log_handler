import json
import traceback
from logging import Handler, CRITICAL, ERROR, WARNING, INFO, FATAL, DEBUG, NOTSET, Formatter

import requests.exceptions
import six
import slacker

ERROR_COLOR = 'danger'  # color name is built in to Slack API
WARNING_COLOR = 'warning'  # color name is built in to Slack API
INFO_COLOR = '#439FE0'

COLORS = {
    CRITICAL: ERROR_COLOR,
    FATAL: ERROR_COLOR,
    ERROR: ERROR_COLOR,
    WARNING: WARNING_COLOR,
    INFO: INFO_COLOR,
    DEBUG: INFO_COLOR,
    NOTSET: INFO_COLOR,
}

DEFAULT_EMOJI = ':heavy_exclamation_mark:'


class NoStacktraceFormatter(Formatter):
    """
    By default the stacktrace will be formatted as part of the message.
    Since we want the stacktrace to be in the attachment of the Slack message,
     we need a custom formatter to leave it out of the message
    """

    def formatException(self, ei):
        return None

    def format(self, record):
        # Work-around for https://bugs.python.org/issue29056
        saved_exc_text = record.exc_text
        record.exc_text = None
        try:
            return super(NoStacktraceFormatter, self).format(record)
        finally:
            record.exc_text = saved_exc_text


class SlackerLogHandler(Handler):
    def __init__(self, api_key, channel, stack_trace=True, username='Python logger', icon_url=None, icon_emoji=None,
                 fail_silent=False, ping_users=None, ping_level=None):
        Handler.__init__(self)
        self.formatter = NoStacktraceFormatter()

        self.stack_trace = stack_trace
        self.fail_silent = fail_silent

        self.slacker = slacker.Slacker(api_key)

        self.username = username
        self.icon_url = icon_url
        self.icon_emoji = icon_emoji if (icon_emoji or icon_url) else DEFAULT_EMOJI
        self.channel = channel
        if not self.channel.startswith('#') and not self.channel.startswith('@'):
            self.channel = '#' + self.channel

        self.ping_level = ping_level
        self.ping_users = []

        if ping_users:
            user_list = self.slacker.users.list().body['members']

            for ping_user in ping_users:
                ping_user = ping_user.lstrip('@')

                for user in user_list:
                    if user['name'] == ping_user:
                        self.ping_users.append(user['id'])
                        break
                else:
                    raise RuntimeError('User not found in Slack users list: %s' % ping_user)



    def build_msg(self, record):
        return six.text_type(self.format(record))

    def build_trace(self, record, fallback):
        trace = {
            'fallback': fallback,
            'color': COLORS.get(self.level, INFO_COLOR)
        }

        if record.exc_info:
            trace['text'] = '\n'.join(traceback.format_exception(*record.exc_info))

        return trace

    def emit(self, record):
        message = self.build_msg(record)

        if self.ping_users and record.levelno >= self.ping_level:
            for user in self.ping_users:
                message = '<@%s> %s' % (user, message)

        if self.stack_trace:
            trace = self.build_trace(record, fallback=message)
            attachments = json.dumps([trace])
        else:
            attachments = None

        try:
            self.slacker.chat.post_message(
                text=message,
                channel=self.channel,
                username=self.username,
                icon_url=self.icon_url,
                icon_emoji=self.icon_emoji,
                attachments=attachments,
            )
        except requests.exceptions.HTTPError as e:
            if self.fail_silent:
                pass
            else:
                raise e
        except slacker.Error as e:
            if self.fail_silent:
                pass
            else:
                raise e
