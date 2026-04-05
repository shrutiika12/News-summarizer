import streamlit as st
from gnews import GNews
import requests as req
from rouge_score import rouge_scorer
import nltk
import random
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.tag import pos_tag

st.set_page_config(
    page_title="AI News Summarizer",
    page_icon="📰",
    layout="wide"
)

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

# ─────────────────────────────────────────
# Hugging Face API (no torch needed!)
# ─────────────────────────────────────────
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
HF_HEADERS = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}

def summarize_via_api(text):
    words = text.split()
    if len(words) < 30:
        return text
    if len(words) > 700:
        text = ' '.join(words[:700])
    try:
        response = req.post(
            HF_API_URL,
            headers=HF_HEADERS,
            json={"inputs": text, "parameters": {"max_length": 80, "min_length": 20}}
        )
        result = response.json()
        if isinstance(result, list):
            return result[0]['summary_text']
        elif 'error' in result:
            return f"API error: {result['error']}"
        return text
    except Exception as e:
        return f"Error: {e}"

# ─────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────
def fetch_news(topic, num_articles=5):
    google_news = GNews(language='en', country='IN', max_results=num_articles)
    raw_articles = google_news.get_news(topic)
    articles = []
    for item in raw_articles:
        try:
            title = item.get('title', '')
            description = item.get('description', '')
            full_text = title + ". " + description
            if len(full_text) > 30:
                articles.append({
                    'title': title,
                    'text': full_text,
                    'url': item.get('url', ''),
                    'source': item['publisher']['title']
                })
        except Exception:
            pass
    return articles


def generate_mcqs(summary, num_questions=3):
    stop_words = set(stopwords.words('english'))
    sentences = sent_tokenize(summary)
    mcqs = []
    used_answers = set()
    for sentence in sentences[:num_questions]:
        words = word_tokenize(sentence)
        tagged = pos_tag(words)
        candidates = [
            word for word, tag in tagged
            if tag in ('NN', 'NNP', 'NNS', 'NNPS', 'CD')
            and word.lower() not in stop_words
            and len(word) > 2
            and word not in used_answers
        ]
        if not candidates:
            continue
        answer = random.choice(candidates)
        used_answers.add(answer)
        question = sentence.replace(answer, "______")
        all_words = word_tokenize(summary)
        all_tagged = pos_tag(all_words)
        wrong_pool = list(set([
            word for word, tag in all_tagged
            if tag in ('NN', 'NNP', 'NNS', 'NNPS', 'CD')
            and word.lower() not in stop_words
            and len(word) > 2
            and word != answer
        ]))
        if len(wrong_pool) < 3:
            continue
        wrong_options = random.sample(wrong_pool, 3)
        options = wrong_options + [answer]
        random.shuffle(options)
        mcqs.append({
            'question': question,
            'options': options,
            'answer': answer
        })
    return mcqs


def calculate_rouge(generated, reference):
    scorer = rouge_scorer.RougeScorer(
        ['rouge1', 'rouge2', 'rougeL'],
        use_stemmer=True
    )
    scores = scorer.score(reference, generated)
    return {
        'rouge1': round(scores['rouge1'].fmeasure, 4),
        'rouge2': round(scores['rouge2'].fmeasure, 4),
        'rougeL': round(scores['rougeL'].fmeasure, 4)
    }


# ─────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────
st.title("📰 AI News Summarizer")
st.markdown("*Fetch live news → AI summarizes → Auto-generates MCQs for exam prep*")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Settings")
    num_articles = st.slider("Number of articles", 1, 10, 5)
    num_mcqs = st.slider("MCQs per article", 1, 5, 3)
    st.markdown("---")
    st.markdown("Built with Hugging Face BART + GNews API")

topic = st.text_input(
    "🔍 Enter a news topic",
    placeholder="e.g. cricket, India economy, technology..."
)

if st.button("🚀 Generate Summaries & MCQs", type="primary"):
    if not topic:
        st.warning("Please enter a topic first!")
    else:
        with st.spinner(f"📡 Fetching news about '{topic}'..."):
            articles = fetch_news(topic, num_articles)

        if not articles:
            st.error("No articles found. Try a different topic!")
        else:
            st.success(f"✅ Fetched {len(articles)} articles!")
            all_scores = []

            for i, article in enumerate(articles):
                st.markdown("---")
                st.subheader(f"📌 Article {i+1}: {article['title'][:70]}...")
                st.caption(f"Source: {article['source']} | [Read full article]({article['url']})")

                with st.spinner("🤖 Summarizing..."):
                    summary = summarize_via_api(article['text'])

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**📄 Original Text**")
                    st.info(article['text'])
                with col2:
                    st.markdown("**✨ AI Summary**")
                    st.success(summary)

                scores = calculate_rouge(summary, article['text'])
                all_scores.append(scores)

                st.markdown(
                    f"📊 **ROUGE Scores** — "
                    f"ROUGE-1: `{scores['rouge1']}` | "
                    f"ROUGE-2: `{scores['rouge2']}` | "
                    f"ROUGE-L: `{scores['rougeL']}`"
                )

                st.markdown("**❓ Practice MCQs**")
                mcqs = generate_mcqs(summary, num_mcqs)

                if not mcqs:
                    st.warning("Not enough content to generate MCQs.")
                else:
                    for j, mcq in enumerate(mcqs):
                        st.markdown(f"**Q{j+1}: {mcq['question']}**")
                        selected = st.radio(
                            f"Choose answer for Q{j+1}",
                            mcq['options'],
                            key=f"q_{i}_{j}",
                            label_visibility="collapsed"
                        )
                        if selected == mcq['answer']:
                            st.success("✅ Correct!")
                        else:
                            st.error(f"❌ Wrong! Answer is: {mcq['answer']}")

            if all_scores:
                st.markdown("---")
                st.subheader("📊 Overall ROUGE Score Summary")
                avg1 = round(sum(s['rouge1'] for s in all_scores) / len(all_scores), 4)
                avg2 = round(sum(s['rouge2'] for s in all_scores) / len(all_scores), 4)
                avgL = round(sum(s['rougeL'] for s in all_scores) / len(all_scores), 4)

                c1, c2, c3 = st.columns(3)
                c1.metric("Avg ROUGE-1", avg1)
                c2.metric("Avg ROUGE-2", avg2)
                c3.metric("Avg ROUGE-L", avgL)

                st.info(
                    f'📝 Resume line: "Achieving summarization accuracy of '
                    f'ROUGE score {avg1} across {len(articles)} articles processed"'
                )