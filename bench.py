import argparse
import asyncio
import aiohttp
import time
import re
import sys

URL_PATTERN = re.compile(r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/.*)?$')


async def fetch(session: aiohttp.ClientSession, url: str) -> dict:
    """Выполняет запрос и возвращает статистику выполнения."""
    start_time = time.monotonic()
    try:
        async with session.get(url) as response:
            await response.read()
            elapsed = time.monotonic() - start_time
            status = response.status

            is_success = 200 <= status < 400
            is_failed = status >= 400

            return {
                "success": is_success,
                "failed": is_failed,
                "error": False,
                "time": elapsed
            }
    except aiohttp.ClientError as e:
        return {"success": False, "failed": False, "error": True, "time": 0.0,
                "error_msg": f"Ошибка соединения: {str(e)}"}
    except asyncio.TimeoutError:
        return {"success": False, "failed": False, "error": True, "time": 0.0,
                "error_msg": "Превышено время ожидания (Timeout)"}
    except Exception as e:
        return {"success": False, "failed": False, "error": True, "time": 0.0,
                "error_msg": f"Неизвестная ошибка: {str(e)}"}


async def benchmark_host(session: aiohttp.ClientSession, host: str, count: int) -> str:
    """Запускает count запросов к одному хосту параллельно и формирует итоговый текст."""
    tasks = [fetch(session, host) for _ in range(count)]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if r["failed"])
    errors = sum(1 for r in results if r["error"])

    times = [r["time"] for r in results if not r["error"]]

    min_time = min(times) if times else 0.0
    max_time = max(times) if times else 0.0
    avg_time = sum(times) / len(times) if times else 0.0

    output = []
    output.append("-" * 40)
    output.append(f"Host: {host}")
    output.append(f"Success: {success}")
    output.append(f"Failed: {failed}")
    output.append(f"Errors: {errors}")
    output.append(f"Min: {min_time:.4f}s")
    output.append(f"Max: {max_time:.4f}s")
    output.append(f"Avg: {avg_time:.4f}s")

    error_msgs = set(r.get("error_msg") for r in results if r.get("error_msg"))
    if error_msgs:
        output.append(f"Зафиксированные ошибки: {', '.join(error_msgs)}")

    return "\n".join(output)


async def main_async(hosts: list, count: int, output_file: str = None):
    """Основная асинхронная функция, управляющая сессией."""
    async with aiohttp.ClientSession() as session:
        tasks = [benchmark_host(session, host, count) for host in hosts]
        results = await asyncio.gather(*tasks)

        final_output = "\n".join(results) + "\n" + ("-" * 40)

        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(final_output)
                print(f"Результаты успешно сохранены в файл: {output_file}")
            except Exception as e:
                print(f"Ошибка при записи в файл {output_file}: {e}")
        else:
            print(final_output)


def parse_and_validate_args():
    parser = argparse.ArgumentParser(description="Утилита для нагрузочного тестирования HTTP серверов.")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-H', '--hosts', type=str,
                       help='Список хостов через запятую (например, https://ya.ru,https://google.com)')
    group.add_argument('-F', '--file', type=str, help='Путь до файла со списком адресов (каждый с новой строки)')

    parser.add_argument('-C', '--count', type=int, default=1, help='Количество запросов на каждый хост')

    parser.add_argument('-O', '--output', type=str, help='Путь до файла для сохранения результатов вывода')

    args = parser.parse_args()

    if args.count <= 0:
        print("Ошибка: Параметр --count должен быть положительным числом.")
        sys.exit(1)

    hosts = []
    if args.hosts:
        hosts = [h.strip() for h in args.hosts.split(',')]
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                hosts = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Ошибка: Файл {args.file} не найден.")
            sys.exit(1)

    invalid_hosts = [h for h in hosts if not URL_PATTERN.match(h)]
    if invalid_hosts:
        print(f"Ошибка: Следующие адреса имеют неверный формат: {', '.join(invalid_hosts)}")
        print("Формат должен быть вида https://example.com")
        sys.exit(1)

    return hosts, args.count, args.output


def main():
    hosts, count, output_file = parse_and_validate_args()

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main_async(hosts, count, output_file))
    except KeyboardInterrupt:
        print("\nТестирование прервано пользователем.")


if __name__ == "__main__":
    main()
