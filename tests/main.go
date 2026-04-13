package main

import (
	"fmt"
	"net/http"
)

func main() {
	address := "http://127.0.0.1:5000/?q=iran&days=30&source=Fox+News&sort=coverage"

	client := &http.Client{}

	req, err := http.NewRequest("GET", address, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return
	}

	// Set headers
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7")
	req.Header.Set("Accept-Encoding", "gzip, deflate, br, zstd")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	req.Header.Set("Cache-Control", "max-age=0")
	req.Header.Set("Connection", "keep-alive")
	req.Header.Set("Cookie", "session=.eJyrVkrJLC7ISayMz0vMTVWyUkpEA0o6SgVFqWmpRUWpKfElGalgRTmZ6RklQJnS4tSi-NTcxMwcFJ0OSXCgVAsAyowi6g.ad0y7Q.evl-xAyOv3YVtKzdNOILa3AWc0c")
	req.Header.Set("Host", "127.0.0.1:5000")
	req.Header.Set("Referer", "http://127.0.0.1:5000/?q=iran&days=30&source=Fox+News&sort=time")
	req.Header.Set("sec-ch-ua", `"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"`)
	req.Header.Set("sec-ch-ua-mobile", "?0")
	req.Header.Set("sec-ch-ua-platform", `"Windows"`)
	req.Header.Set("sec-fetch-dest", "document")
	req.Header.Set("sec-fetch-mode", "navigate")
	req.Header.Set("sec-fetch-site", "same-origin")
	req.Header.Set("sec-fetch-user", "?1")
	req.Header.Set("upgrade-insecure-requests", "1")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36")

	for i := 1; ; i++ {
		resp, err := client.Do(req)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
		} else {
			fmt.Printf("Status: %s\n", resp.Status)
			resp.Body.Close()
		}
		//time.Sleep(1 * time.Nanosecond)
	}
}
