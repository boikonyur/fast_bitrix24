from itertools import chain

from beartype.typing import Dict, List, Union


class ErrorInServerResponseException(Exception):
    pass


class ServerResponseParser:
    def __init__(self, response: dict, get_by_ID: bool = False):
        self.response = response
        self.get_by_ID = get_by_ID

    def more_results_expected(self, total: int) -> bool:
        return (
            total > len(self.extract_results())
        )

    @property
    def result(self):
        return self.response.get("result")

    @property
    def total(self):
        return self.response.get("total")

    @property
    def error_description(self):
        return self.response.get("error_description")

    @property
    def result_error(self):
        return self.response.get("result_error")

    def extract_results(self) -> Union[Dict, List[Dict]]:
        """Вернуть результаты запроса.

        Если определено, что запрос был батчевым, то разобрать результаты батчей
        и собрать их в плоский список.

        Returns:
            Any: Результаты запроса, по возможности превращенные в плоский список.
        """
        self.raise_for_errors()

        if not self.is_batch():
            return self.extract_from_single_response(self.result)

        if not self.get_by_ID:  # Почему? Откуда это правило?
            return self.extract_from_batch_response(self.result["result"])

        extracted = self.extract_from_single_response(self.result["result"])

        return (
            extracted[0]
            if isinstance(extracted, list) and len(extracted) == 1
            else extracted
        )

    def raise_for_errors(self):
        errors = self.extract_errors()
        if errors:
            raise ErrorInServerResponseException(errors)

    def extract_errors(self):
        if self.is_batch():
            if self.result.get("result_error"):
                return self.result["result_error"]
        elif self.result_error:
            return self.result_error

        return None

    def is_batch(self) -> bool:
        return isinstance(self.result, dict) and "result" in self.result

    def extract_from_single_response(self, result):
        # Сначала проверяем, является ли result списком
        if isinstance(result, list):
            return result

        # если результат вызова содержит только словарь из одного элемента {ключ: содержимое},
        # то вернуть это содержимое.
        # См. https://github.com/leshchenko1979/fast_bitrix24/issues/132

        # метод `crm.stagehistory.list` возвращает dict["items", list] --
        # разворачиваем его в список
        return next(iter(result.values())) if self.is_nested(result) else result

    @staticmethod
    def is_nested(result) -> bool:
        return isinstance(result, dict) and len(result.values()) == 1

    def extract_from_batch_response(self, result) -> list:
        if not result:
            return []

        # если результат вызова содержит только словарь c одним ключом
        # и списком у него внутри, то вернуть этот список.
        # См. https://github.com/leshchenko1979/fast_bitrix24/issues/132

        first_item = next(iter(result.values()))

        # Если первый элемент - простое значение (не словарь/список),
        # возвращаем само значение
        if not isinstance(first_item, (dict, list)):
            return first_item

        # если внутри - списки, то вернуть их в одном плоском списке
        if self.is_nested(first_item) or isinstance(first_item, list):
            result_list = [
                self.extract_from_single_response(element)
                for element in result.values()
            ]

            # если получился вложенный список, то уплощаем
            if isinstance(result_list[0], list):
                result_list = list(chain(*result_list))

            return result_list

        # иначе (если внутри - dict), то вернуть сам dict
        return result
