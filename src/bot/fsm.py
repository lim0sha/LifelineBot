from aiogram.fsm.state import StatesGroup, State


class AdviceStates(StatesGroup):
    in_advice_mode = State()


class AnonymousStates(StatesGroup):
    waiting_for_message = State()


class MeetingStates(StatesGroup):
    selecting_mentor = State()
    waiting_for_message = State()


class ProfileStates(StatesGroup):
    selecting_field = State()
    editing_field = State()
