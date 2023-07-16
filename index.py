from random import randrange

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

from config import token, user_token
from database import save_vk_user, find_history_couples_id_by_user_id, add_couple_in_history

vk = vk_api.VkApi(token=token)
user_vk = vk_api.VkApi(token=user_token)
long_poll = VkLongPoll(vk)

POSSIBLE_COUPLES_FOR_CLIENTS = {}

START_COMMAND = "поиск"
CONTINUE_COMMAND = "/далее"


def send_msg(user_id, message):
    vk.method("messages.send", {"user_id": user_id, "message": message, "random_id": randrange(10 ** 7), })


def send_msg_with_photo(user_id, message, photo_id):
    vk.method("messages.send", {"user_id": user_id, "message": message, "random_id": randrange(10 ** 7),
                                "attachment": f"photo{photo_id}", })


def user_profile_is_closed(user_id):
    response = vk.method("users.get", {"user_id": user_id, "fields": "is_closed"})
    return response[0].get("is_closed")


def get_user_data_by_id(user_id):
    response = vk.method("users.get", {"user_id": user_id, "fields": "sex,bdate,city,relation"})[0]
    try:
        return {"user_id": response.get("id"), "sex": response.get("sex"), "age": response.get("age"),
                "city_id": response.get("city").get("id")}
    except AttributeError:
        return None


def get_user_popular_photos_by_user_id(user_id):
    try:
        response = user_vk.method("photos.get", {"owner_id": user_id, "album_id": "profile", "extended": 1})
        photos = []
        for i in response.get("items"):
            temp = {"photo_id": f"{i.get('owner_id')}_{i.get('id')}", "likes_count": i.get("likes").get("count"),
                    "comments_count": i.get("comments").get("count")}
            photos.append(temp)
        photos.sort(key=lambda dictionary: dictionary["likes_count"], reverse=True)
        return photos[:3]
    except vk_api.exceptions.ApiError:
        pass


def search_possible_couples_for_user(user_id):
    global POSSIBLE_COUPLES_FOR_CLIENTS
    user_data = get_user_data_by_id(user_id)
    request_data = {"count": 100, "status": 6}
    if user_data.get("age") is not None:
        request_data.update({"age_from": user_data.get("age") - 5})
        request_data.update({"age_to": user_data.get("age") + 5})
    if user_data.get("city_id") is not None:
        request_data.update({"city_id": user_data.get("city_id")})
    need_sex = 0
    if user_data.get("sex") == 1:
        need_sex = 2
    elif user_data.get("sex") == 2:
        need_sex = 1
    request_data.update({"sex": need_sex})
    response = user_vk.method("users.search", request_data)
    possible_couples_id = []
    history_couples_id = find_history_couples_id_by_user_id(user_id)
    for i in response.get("items"):
        if user_profile_is_closed(i.get("id")) is False and i.get("id") not in history_couples_id:
            possible_couples_id.append(i.get("id"))
    POSSIBLE_COUPLES_FOR_CLIENTS.update({user_id: possible_couples_id})


def find_couple_for_user(user_id):
    global POSSIBLE_COUPLES_FOR_CLIENTS
    possible_couples = POSSIBLE_COUPLES_FOR_CLIENTS.get(user_id)
    if possible_couples is not None and len(possible_couples) > 0:
        possible_couple_id = possible_couples.pop(0)
        add_couple_in_history(user_id, possible_couple_id)
        POSSIBLE_COUPLES_FOR_CLIENTS.update({user_id: possible_couples})
        return possible_couple_id
    else:
        return None


def get_domain_by_user_id(user_id):
    response = vk.method("users.get", {"user_id": user_id, "fields": "domain"})
    return f"vk.com/{response[0].get('domain')}"


def is_start_request(text):
    if text.lower() == START_COMMAND:
        return True
    else:
        return False


def is_continue_request(text):
    if text.lower() == CONTINUE_COMMAND:
        return True
    else:
        return False


for event in long_poll.listen():
    if event.type == VkEventType.MESSAGE_NEW:
        if event.to_me:
            msg_text = event.text
            client_user_id = event.user_id
            if user_profile_is_closed(client_user_id):
                send_msg(client_user_id, "Ваш профиль закрыт, для работы VKinder откройте профиль")
            else:
                if is_start_request(msg_text):
                    save_vk_user(client_user_id)
                    search_possible_couples_for_user(client_user_id)
                    send_msg(event.user_id,
                             f"Мы нашли подходящие анкеты, пожалуйста воспользуйтесь командой {CONTINUE_COMMAND} для "
                             f"просмотра "
                             f"{START_COMMAND}")
                elif is_continue_request(msg_text):
                    couple = find_couple_for_user(client_user_id)
                    if couple is None:
                        send_msg(event.user_id,
                                 f"Мы не смогли подобрать вам пару, возможно список анкет закончился, попробуйте "
                                 f"{START_COMMAND}")
                    else:
                        send_msg(event.user_id,
                                 f"Мы подобрали вам пару! {get_domain_by_user_id(couple)}")
                        couple_photos = get_user_popular_photos_by_user_id(couple)
                        for photo in couple_photos:
                            send_msg_with_photo(event.user_id, "Фото", photo.get("photo_id"))
                        send_msg(event.user_id,
                                 f"Чтобы показать следующую анкету введите "
                                 f"{CONTINUE_COMMAND}")
                else:
                    send_msg(event.user_id, f"Привет, для поиска необходимо написать {START_COMMAND}")
