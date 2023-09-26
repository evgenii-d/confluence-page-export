''' Export Confluence pages for given ID while preserving the hierarchy '''
from pathlib import Path
import sys
import json
import logging
import requests

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s | %(levelname)s | %(message)s')


class Confluence:
    ''' Confluence API wrapper '''

    def __init__(self, url, username, password) -> None:
        self.url = url
        self.username = username
        self.password = password

        self.session = requests.Session()
        self.session.auth = (username, password)

    def get_page_by_id(self, page_id: str) -> dict:
        ''' Get page by ID '''
        api = f'{self.url}/wiki/api/v2/pages/{page_id}'
        result = self.session.get(api)
        return result.json()

    def get_page_ancestors(self, page_id: str) -> list:
        ''' Returns all ancestors for a given page by ID '''
        api = f'{self.url}/wiki/api/v2/pages/{page_id}/ancestors'
        result = self.session.get(api)
        return result.json()['results']

    def get_page_children(self, page_id: str) -> list:
        ''' Returns all child pages for given page ID '''
        api = f'{self.url}/wiki/api/v2/pages/{page_id}/children'
        result = self.session.get(api)
        return result.json()['results']

    def get_all_child_pages(self, page_id: str) -> list:
        ''' Returns all child pages for given page ID '''
        children = self.get_page_children(page_id)
        pages = []

        for child in children:
            sys.stdout.write('Add ID ' + child['id'])
            sys.stdout.flush()
            sys.stdout.write('\r')

            pages.append(child)
            pages.extend(self.get_all_child_pages(child['id']))

        return pages

    def secure_string(self, string: str) -> str:
        ''' Remove characters that might affect the filename '''
        result = ''.join(char for char in string if (
            char.isalnum() or char in '._- '))
        return result

    def page_to_doc(self, page_id: str, dir_path: Path | str) -> None:
        ''' Save page as doc '''
        page_title = self.get_page_by_id(page_id)['title']
        file_name = self.secure_string(f'{page_title}_{page_id}.doc')
        export_api = f'{self.url}/wiki/exportword?pageId={page_id}'

        content = self.session.get(export_api).content
        Path(dir_path).mkdir(exist_ok=True, parents=True)

        try:
            with open(dir_path/file_name, 'wb',) as file:
                file.write(content)
            logging.info('Page %s saved', page_id)
        except requests.exceptions.ReadTimeout:
            logging.warning('Timeout error: page ID - %s', page_id)
        except requests.exceptions.HTTPError:
            logging.warning('HTTPError error: page ID - %s', page_id)
        except OSError:
            logging.warning('Filename error: page ID - %s', page_id)


def main():
    ''' Entry point '''
    try:
        with open(Path(__file__).parent/'config.json', 'r', encoding='utf-8') as file:
            config = json.load(file)

        if config.keys() != {'url', 'email', 'token', 'pageId'}:
            raise KeyError
    except FileNotFoundError:
        sys.exit('config.json not found')
    except (json.decoder.JSONDecodeError, KeyError, AttributeError):
        sys.exit('Invalid config.json')

    output_dir = Path(__file__).parent/'output'
    root_page_id = config['pageId']
    confluence = Confluence(
        url=config['url'],
        username=config['email'],
        password=config['token'])

    pages = confluence.get_all_child_pages(root_page_id)
    if len(pages) == 0:
        sys.exit('Child pages not found')

    confluence.page_to_doc(root_page_id, output_dir)

    for page in pages:
        ancestor_ids = []
        ancestor_titles = []
        page_full_path = []

        for ancestor in confluence.get_page_ancestors(page['id']):
            ancestor_ids.append(ancestor['id'])
            title = confluence.get_page_by_id(ancestor['id'])['title']
            ancestor_titles.append(confluence.secure_string(title))

        root_index = ancestor_ids.index(root_page_id)
        for index, item in enumerate(ancestor_ids[root_index:], start=root_index):
            page_full_path.append(f'{ancestor_titles[index]}_{item}')

        confluence.page_to_doc(page['id'], output_dir/'/'.join(page_full_path))


if __name__ == '__main__':
    main()
