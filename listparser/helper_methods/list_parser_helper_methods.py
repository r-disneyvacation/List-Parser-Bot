import praw
import re
import requests
from bs4 import BeautifulSoup
from helper_methods.enums import ArticleType, convert_enum_to_string
from langdetect import detect, lang_detect_exception
from os import environ


# If the list article title contains any of the words below, the list will not be posted to Reddit.
# This avoids posting content which contains lists of ads and images.
BREAK_WORDS = ['pictures', 'pics', 'photos', 'gifs', 'images',
               'twitter', 'must see', 'tweets', 'memes',
               'instagram', 'tumblr', 'gifts', 'products', 'deals']


def connect_to_reddit():
    """Connects the bot to the Reddit client."""

    return praw.Reddit(client_id=environ["BUZZFEEDBOT_CLIENT_ID"],
                       client_secret=environ["BUZZFEEDBOT_CLIENT_SECRET"],
                       user_agent=environ["BUZZFEEDBOT_USER_AGENT"],
                       username=environ["BUZZFEEDBOT_USERNAME"],
                       password=environ["BUZZFEEDBOT_PASSWORD"])


def soup_session(link):
    """BeautifulSoup session."""
    session = requests.Session()
    daily_archive = session.get(link)
    soup = BeautifulSoup(daily_archive.content, 'html.parser')
    return soup


def post_to_reddit(headline, main_text, link, subreddit, website):
    """Module that takes the title, main text and link to article and posts directly to Reddit."""

    reddit = connect_to_reddit()

    reddit.subreddit(subreddit).submit(title=headline, selftext=main_text+'\n' + '[Link to article](' + link + ')')\
                               .mod.flair(text=convert_enum_to_string(website))


def post_previously_made(post_title, list_elements, subreddit):
    """
    Checks if the post has already been submitted.
    This is done by comparing a post with the same list count has 4 or more of the same words in the title.
    Returns True if post was already submitted. Returns False otherwise.
    """

    reddit = connect_to_reddit()
    subreddit = reddit.subreddit(subreddit)
    submissions = subreddit.new(limit=10)
    for submission in submissions:
        if submission.title.lower() == post_title:
            return True
        try:
            list_elements_to_check = [int(s) for s in submission.title.split() if s.isdigit()][0]
        except IndexError:
            continue
        if list_elements_to_check == list_elements:
            same_words = set.intersection(set(post_title.split()), set(submission.title.lower().split()))
            number_of_words = len(same_words)
            if number_of_words >= 4:
                return True

    return False


def get_article_list_count(article_title):
    """Gets number of points in the list article."""

    try:
        no_of_elements = [int(s) for s in article_title.split() if s.isdigit()][0]
    except (AttributeError, IndexError):
        return 0

    return no_of_elements


def article_title_meets_posting_requirements(subreddit, website, article_title):
    """
    Validates that the article title meets all requirements to post the list to Reddit.

    The validations below check if:
        (1) The article contains a number
        (2) The post hasn't been made already
        (3) The article title doesn't contain certain pre-defined keywords
        (4) The article title is in english (BuzzFeed only)

    Returns True if all validations are met. Returns False otherwise.
    """

    if website == ArticleType.BuzzFeed:
        try:
            if not detect(article_title) == 'en':
                return False
        except lang_detect_exception.LangDetectException:
            return False

    no_of_elements = get_article_list_count(article_title)
    if no_of_elements == 0:
        return False

    article_title_lowercase = article_title.lower()
    if any(words in article_title_lowercase for words in BREAK_WORDS):
        return False

    if post_previously_made(article_title_lowercase, no_of_elements, subreddit):
        return False

    return True


def article_text_meets_posting_requirements(website, article_list_text, list_counter, total_elements):
    """
    Validates that the article text meets all requirements to post the list to Reddit.

    The validations below check if:
        (1) The header count is equal to the list article count
        (2) The list is correctly formatted
        (3) The article resembles an ad based on specific regex validation (BuzzFeed only)

    Returns True if all validations are met. Returns False otherwise.
    """

    if list_counter-1 != total_elements:
        return False

    if not is_correctly_formatted_list(article_list_text, list_counter):
        return False

    if website == ArticleType.BuzzFeed:
        percentage_threshold = 0.50  # Max percentage of regex validated ad-like list items where the post will not be made.
        if (len(re.findall('(\[A(n)? |\[(Up to )?[0-9]{2}% |\[This )', article_list_text)) / total_elements) >= percentage_threshold:
            return False

    return True


def sort_list_numerically(full_list_text, list_count):
    """Sorts concatenated list in numerical order."""

    count_list = []

    for x, y in zip(range(1, list_count), reversed(range(1, list_count))):
        count_list.append([x, y])

    for i, (x, y) in enumerate(count_list):
        count_list[i] = [str(x) + '.', str(y) + '.']

    for i, (start, end) in enumerate(count_list):
        if i <= len(count_list) / 2:
            full_list_text = full_list_text.replace(end, start)
        else:
            full_list_text = start.join(full_list_text.rsplit(end, 1))

    return full_list_text


def is_correctly_formatted_list(full_text, list_count):
    """Checks if the final concatenated list is correctly formatted."""

    list_prefix_numbers = []

    for number in range(1, list_count):
        list_prefix_numbers.append(str(number) + '.')

    return all(element_prefix in full_text for element_prefix in list_prefix_numbers)