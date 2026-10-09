# Run your own Tesserae

This recipe takes a fresh Ubuntu 24.04 machine to a Tesserae of your own, running at http://localhost:5000, with the same search engine, the same corpus and the same indexes as the public site for Latin, Greek, English, Coptic and Hebrew. It uses the public code repository and one data bundle. A second, larger bundle adds Theme Search and Similar Passages.

Tesserae is free for scholarship and teaching. Parts of the data carry non-commercial licences, so do not build a commercial service on it. The file LICENSES.md inside each bundle lists every source and the credit line it requires.

## What you need

- A computer or virtual machine with Ubuntu 24.04, an account that can use sudo, and a network connection.
- Memory. 16 GB is enough for the core bundle. Use 32 GB if you add the full bundle.
- Disk space. Allow 60 GB free for the core bundle and 120 GB free for the full bundle. The download is compressed and the unpacked data is several times larger.
- About an hour for the core bundle, most of it download and unpacking time.

## Part 1. The core bundle

The core bundle holds the texts, the lemma caches, the search indexes, the word-pair tables, the aligned translations that are public domain or openly licensed, the inscriptions and papyri collection for Latin and Greek, and the credits.

1. Install the system packages.

   ```
   sudo apt update
   sudo apt install -y git curl zstd build-essential python3.12 python3.12-venv python3-dev libpq-dev
   ```

2. Install Node.js 20, which builds the web pages.

   ```
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt install -y nodejs
   ```

3. Fetch the code.

   ```
   git clone https://github.com/tesserae/tesserae-v6.git
   cd tesserae-v6
   git checkout <COMMIT>
   ```

   The Downloads page names the commit next to the bundle. The data was built for that version of the code, and a newer checkout may hold texts the bundle does not match.

4. Make a Python environment and install the web application's packages. The list leaves out the two machine-learning packages (sentence-transformers and stanza) because the web application does not use them. Only the encoder service in Part 2 does.

   ```
   python3.12 -m venv venv
   venv/bin/pip install --upgrade pip
   grep -v -E '^(sentence-transformers|stanza)' requirements.txt > /tmp/requirements-web.txt
   venv/bin/pip install -r /tmp/requirements-web.txt
   ```

5. Download the core bundle and its checksum file from the address given on the Tesserae Downloads page. Replace the placeholders with the address and the date in the file name.

   ```
   curl -L -O "<BUNDLE_ADDRESS>/tesserae-public-core-<DATE>.tar.zst"
   curl -L -O "<BUNDLE_ADDRESS>/tesserae-public-core-<DATE>.tar.zst.sha256"
   ```

6. Check that the download is intact. The command must print OK.

   ```
   sha256sum -c tesserae-public-core-<DATE>.tar.zst.sha256
   ```

7. Unpack the bundle into the checkout. The bundle files go into the folders where the application looks for them. Texts that the repository already holds are overwritten with identical or newer copies.

   ```
   tar --zstd -xf tesserae-public-core-<DATE>.tar.zst -C .
   ```

8. Read LICENSES.md, which the unpacking placed in the checkout. It names the credit lines you must keep if you pass any of the data on.

9. Write the settings file. A local copy needs no secrets. The database setting uses a small file-based database, which holds only your own saved searches.

   ```
   cat > .env <<'EOF'
   DEPLOYMENT_ENV=dev
   DATABASE_URL=sqlite:///tesserae_local.db
   PORT=5000
   EOF
   ```

10. Build the web pages. Run this from the top folder of the checkout.

    ```
    npm ci
    npm run build
    ```

11. Start the application.

    ```
    venv/bin/python main.py
    ```

    Leave this running. Open http://localhost:5000 in a browser. The first search of a language takes longer because the index loads into memory. The application listens on every network interface of the machine, so keep the machine behind a firewall unless you mean to share it.

12. Check that it works. Open a second terminal in the same folder and run the reference check. It searches for the phrase "arma virum" and fails if Vergil, Ovid, Livy, Quintilian or Seneca are missing from the results. The same test is described in tests/search_reference_tests.md.

    ```
    venv/bin/python scripts/reference_search_check.py --base-url http://localhost:5000
    ```

    The command ends with a pass for every check. If one fails, stop and read the message before going on.

## Part 2. The full bundle (Theme Search and Similar Passages)

Theme Search finds passages by what they are about, in plain English. Similar Passages and the Reader's connection gutter compare passages by meaning. Both need the passage index, the line vectors and a small encoder service. The full bundle contains everything in the core bundle plus these files, so it can be used alone or unpacked over the core files.

13. Stop the application with Ctrl+C. Download the full bundle and its checksum, check it as in step 6, and unpack it the same way.

    ```
    curl -L -O "<BUNDLE_ADDRESS>/tesserae-public-full-<DATE>.tar.zst"
    curl -L -O "<BUNDLE_ADDRESS>/tesserae-public-full-<DATE>.tar.zst.sha256"
    sha256sum -c tesserae-public-full-<DATE>.tar.zst.sha256
    tar --zstd -xf tesserae-public-full-<DATE>.tar.zst -C .
    ```

14. Make a second Python environment for the encoder. It needs PyTorch, which is large, so use the processor-only build unless you have a graphics card.

    ```
    python3.12 -m venv venv-encoder
    venv-encoder/bin/pip install --upgrade pip
    venv-encoder/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
    venv-encoder/bin/pip install sentence-transformers
    ```

15. Start the encoder service on port 8090. It downloads the multilingual-e5-large model from Hugging Face the first time, about 2 GB, and then loads it in about half a minute. Leave it running in its own terminal.

    ```
    venv-encoder/bin/python services/embed_server.py
    ```

    Check it from another terminal. The answer must contain `"loaded": true` once the model has finished loading.

    ```
    curl http://127.0.0.1:8090/health
    ```

16. Start the application again and test Theme Search. The answer should list passages about the plague, with no error field.

    ```
    venv/bin/python main.py
    curl "http://localhost:5000/api/passages/theme-search?q=a+plague+strikes+a+city&limit=5"
    curl "http://localhost:5000/api/passages/status"
    ```

17. Run the reference check from step 12 once more. It must still pass.

## Keeping it running

For a private machine, a terminal window or a `tmux` session for each of the two services is enough. For a shared machine, run the application behind a web server such as Apache or nginx and make each service a systemd unit. The repository's deployment folder shows how the public site does it. That setup is outside this recipe.

## What is not included, and why

- **Persian, Urdu and Arabic.** The site serves Persian and Urdu, and holds Arabic back. The terms for passing these texts on have not been cleared, so their texts, indexes, translations, vectors and passage windows are not in either bundle. Searches in those languages will not work on your copy.
- **Italian, Old French and Middle High German.** These are small pilot corpora in Theme Search. Their terms have not been checked for this bundle.
- **Texts held under an indexing-only licence.** A text on the registry in data/restricted_texts.json may be searched on the public site but never passed on. The builder refuses to run if that registry has entries until they are removed from the index copies.
- **Translations that are not public domain or openly licensed.** A translation travels only if its own license field says public domain or an open Creative Commons licence with no non-commercial term. For example, the part of the Punica of Silius Italicus that rests on a non-commercial translation stays out.
- **Commentaries, the scholarship caches and the citation index.** Commentary licences differ from text to text, the caches hold answers from third-party services whose terms do not allow passing them on, and the citation index holds sentences quoted from journal articles. These are publisher text, so they are left out and the Scholarship tab shows nothing on your copy.
- **The assistant (Tessa).** It needs a large language model server and, for some features, a university gateway. Neither can be shared.
- **The trained Theme Search reader.** It re-orders the top results. Its training data has not been confirmed to be entirely open, so it is not shared. Theme Search works without it and ranks by vector similarity and keyword match alone.
- **The parsed-sentence databases.** The syntax channels use databases built from treebanks with mixed terms. The script scripts/download_data.py fetches them from the project's data server when that is reachable. Without them the other channels still work.
- **Keys, passwords, user data and the production database.** These never leave the production machine.

## If you are using an AI coding assistant

You can hand this document to an AI coding assistant and ask it to do the installation for you. Open a terminal on the target machine, start the assistant there, and paste the following.

> Install Tesserae on this Ubuntu machine by following docs/RUN_YOUR_OWN.md in https://github.com/tesserae/tesserae-v6, Part 1 only. Run each numbered step in order and show me each command before you run it. Stop and tell me if any step fails or if a checksum does not match. Do not create any account, key or password, and do not change anything outside the tesserae-v6 folder except the packages in step 1 and step 2. Step 5 needs the bundle address, which is <PASTE THE ADDRESS FROM THE DOWNLOADS PAGE>. When you reach step 12, show me the output of the reference check.

When Part 1 passes, paste a second request that names Part 2 and gives the full bundle's file name.

## Checking the data yourself

Each bundle contains MANIFEST.tsv. Every line gives a file's path, its size, its SHA-256 hash and the licence source. To check the unpacked files against it, run this in the checkout.

```
tail -n +2 MANIFEST.tsv | awk -F'\t' '{print $3"  "$1}' | sha256sum -c --quiet
```

The command prints nothing when every file matches. Files you have changed or rebuilt since unpacking will be reported.
