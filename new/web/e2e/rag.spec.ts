import { expect, test } from '@playwright/test'

test('asks the backend and restores the tab-local transcript after reload', async ({ page }) => {
  test.setTimeout(120_000)
  const question = 'Thủ tục đăng ký khai sinh cần những giấy tờ gì?'

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Trợ lý thủ tục hành chính' })).toBeVisible()
  await expect(page.getByRole('note')).toContainText('Corpus hiện ở trạng thái nháp')

  await page.getByLabel('Nội dung câu hỏi').fill(question)
  await page.getByRole('button', { name: 'Gửi câu hỏi' }).click()

  await expect(page.locator('.answer-card')).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.bundle-id')).toContainText('Evidence:')
  await expect(page.locator('.answer-status')).toContainText(
    /Có câu trả lời trích xuất|Cần làm rõ câu hỏi|Chưa đủ dữ liệu/,
  )
  await expect(page.locator('.answer-text')).toContainText('Giấy chứng sinh')
  await page.locator('.citations summary').click()
  await expect(page.locator('.citations')).toContainText('PROC-S01-R0003-F')

  await page.reload()
  await expect(page.getByText(question, { exact: true })).toBeVisible()
  await expect(page.locator('.answer-card')).toBeVisible()
})
